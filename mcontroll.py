import gc, network, onewire, ds18b20
from machine import I2C, Pin, PWM, freq
from time import mktime
import uasyncio as asyncio
gc.collect()                                            #Очищаем RAM
from i2c_ds3231 import DS3231
from timezone import TZONE
from esp_pid import PID
from hcontroll import HeatControl
gc.collect()                                            #Очищаем RAM
from webapp import app, bool_to_str


class Main(HeatControl):
    def __init__(self):
        super().__init__()
        self.DEBUG = True                               #Режим отладки, делаем программу разговорчивой
        self.wifi_led = Pin(2, Pin.OUT, value = 1)      #Pin2, светодиод на плате контроллера
        self.heat = PWM(Pin(5), freq=1000, duty=0)     #Pin12, управление нагревом пола
        self.default_on = Pin(0, Pin.IN)                   #Pin14, кнопка для сброса настроек в дефолт
        self.i2c = I2C(scl=Pin(14), sda=Pin(12), freq=400000)     #Настройка шины i2c
        self.ds = ds18b20.DS18X20(onewire.OneWire(Pin(4)))      #Set Temperature sensors
        #Дефолтные настройки, если файла config.txt не будет обнаружено в системе
        self.default_config = ['AP', 'HEAT_CONTROL', 'roottoor', 3, 'True', 20.0, 50]
        #Дефолтный хещ логина и пароля для web admin (root:root)
        self.default_web = str(b'0242c0436daa4c241ca8a793764b7dfb50c223121bb844cf49be670a3af4dd18')
        if self.exists('config.txt') == False or not self.default_on(): #Eсли файла config.txt не обнаружено в системе создаем его
            print('Create new config.txt file')
            with open('config.txt', 'w') as f:
                for i in range(len(self.default_config)):
                    if i != len(self.default_config)-1:
                        f.write(str(self.default_config[i])+'\n')
                    else:
                        f.write(str(self.default_config[i]))
        if self.exists('root.txt') == False or not self.default_on(): #Eсли файла root.txt не обнаружено в системе создаем его
            print('Create new root.txt file')
            with open('root.txt', 'w') as f:
                f.write(self.default_web)

        with open('config.txt', 'r') as f:
            self.config['MODE_WiFi'] = f.readline().rstrip()      #Режим работы WiFi AP или ST
            self.config['ssid'] = str(f.readline().rstrip())      #SSID для подключения к WiFi
            self.config['wf_pass'] = str(f.readline().rstrip())   #Пароль для подключения к WiFi
            self.config['timezone'] = int(f.readline().rstrip())  #Временная зона
            dst = f.readline().rstrip()                           #True включен переход на зимнее время False - выключен
            self.config['T_ROOM'] =  float(f.readline().rstrip()) #Температура в помещении при которой включиться отопление
            self.config['DAY_POWER'] = int(f.readline().rstrip()) #Уменьшение мощности в дневное время в %
            self.config['DST'] = True if dst == 'True' else False
        self.config['IP'] = None                                  #Дефолтный IP адрес
        self.config['internet_outage'] = True                     #Интернет отключен(значение True)
        if self.config['MODE_WiFi'] == 'AP':
            self._ap_if = network.WLAN(network.AP_IF)
            self.config['WIFI'] = self._ap_if
        elif self.config['MODE_WiFi'] == 'ST':
            self._sta_if = network.WLAN(network.STA_IF)
            self.config['WIFI'] = self._sta_if
        
        self.config['Uptime'] = 0            #Время работы контроллера
        self.config['RTC_DS3231'] = 0x68     #Адрес DS3231 RTC
        self.config['WEB_Debug'] = True      #Режим отладки, делаем web server разговорчивым
        self.config['WIFI_AP'] = ('192.168.4.1', '255.255.255.0', '192.168.4.1', '208.67.222.222')
        self.config['TARIFF_ZONE'] = ((7, 0, 0), (22, 59, 59)) #Тарифнаф зона день с 7 до 22:59
        self.config['DAY_ZONE'] = ((7, 0, 0), (22, 59, 59))    #Дефолтное значение тарифной зоны день
        self.config['SOURCE_TIME'] = 'ntp'   #Настройка DS3231, ntp-сервер NTP, local-часы MK
        self.config['TEMP'] = 18.00          #Начальное значение темратуры в помещении
        self.config['DUTY_MIN'] = 0          #Режим работы ПИД регулятора, минимальный предел
        self.config['DUTY_MAX'] = 90         #Режим работы ПИД регулятора, максимальный предел, установлен в 90% 
                                             #для исключения перегрева нагревателя
        self.config['RTC_TIME'] = (0, 1, 1, 0, 0, 0, 0, 0)  # Дефолтное время
        self.config['WEBPOWER'] = 0          #Начальное значение мощности для вывода на web интерфейс
        self.config['PID_KP'] = 5
        self.config['PID_KI'] = 0.1
        self.config['PID_KD'] = 0.01
        self.config['POWER'] = 0             #Начальное значение мощности нагревателя
        self.config['WEB_TIME'] = None       #Начальное значение для времени передаваемого с веб интерфейса
        self.config['NTP_UPDATE'] = True                    # Разрешаем обновление по NTP
        self.config['RTC']= DS3231(self.i2c, \
                    self.config['RTC_DS3231'], self.config['timezone'], ) #Включаем работу с модулем RTC DS3231
        self.rtc = self.config['RTC']
        self.config['NOW'] = mktime(self.rtc.datetime())
        self.config['HEAT'] = True           #Начальное значение, нагрев включен

        self.tzone = TZONE(self.config['timezone'])     #Включаем поддержку TIME ZONE

        loop = asyncio.get_event_loop()
        loop.create_task(self._heartbeat())              #Индикация подключения WiFi
        loop.create_task(self._collection_temp())        #Сбор информации с температурных датчиков DS18D20
        loop.create_task(self._dataupdate())             # Обновление информации и часы
        #loop.create_task(self._heat_logical())          #Управления отоплением
        #loop.create_task(self._calc_tariff_zone())      #Вычисление тарифных зон
        loop.create_task(self._start_web_app())          #Включаем WEB приложение

    async def _dataupdate(self):
        while True:
            # RTC Update
            self.config['RTC_TIME'] = self.rtc.datetime()
            rtc = self.config['RTC_TIME']
            self.config['NOW'] = mktime(rtc)
            # Проверка летнего или зименего времени каждую минуту в 30с
            if rtc[5] == 30: 
                self.rtc.settime('dht')
            # Если у нас режим подключения к точке доступа и если есть соединение, подводим часы по NTP
            if self.config['MODE_WiFi'] == 'ST' and not self.config['internet_outage']:
                # Подводка часов по NTP каждые сутки в 22:00:00
                if rtc[3] == 22 and rtc[4] == 5 and rtc[5] < 3 and self.config['NTP_UPDATE']:
                        self.config['NTP_UPDATE'] = False
                        self.rtc.settime('ntp')
                        await asyncio.sleep(1)
                        self.config['NTP_UPDATE'] = True
            await asyncio.sleep(1)
    #Логика управления отоплением
    #async def _heat_logical(self):
    #    #Создаем ПИД регулятор
    #    pid = PID(self.config['PID_KP'], self.config['PID_KI'], self.config['PID_KD'], setpoint=self.config['T_ROOM'])
    #    #Устанавливаем минимальный и максимальный предел работы регулятора
    #    pid.output_limits = (self.config['DUTY_MIN'], self.config['DUTY_MAX'])
    #    #Устанавливаем поддерживаемую температуру
    #    t_root = self.config['T_ROOM']
    #    while True:
    #        await asyncio.sleep(3)
    #        if self.config['HEAT']:
    #            #Если тариф дневной зоны, ограничиваем мощность нагрева на self.config['DAY_POWER']%
    #            if self.config['DAY_ZONE'][0] < self.config['RTC'].rtctime()[3:6] and \
    #            self.config['DAY_ZONE'][1] > self.config['RTC'].rtctime()[3:6]:
    #                pid.output_limits = (self.config['DUTY_MIN'], self.config['DAY_POWER'])
    #                self.config['WEBPOWER'] = self.config['DAY_POWER']
    #            else: #Если тариф ночной зоны, разрешаем нагрев до self.config['DUTY_MAX']%
    #                pid.output_limits = (self.config['DUTY_MIN'], self.config['DUTY_MAX'])
    #                self.config['WEBPOWER'] = self.config['DUTY_MAX']
    #            #Если значение поддерживаемой температуры было изменено, применяем изменения
    #            if t_root != self.config['T_ROOM']:
    #                pid.set_setpoint = self.config['T_ROOM']
    #                t_root = self.config['T_ROOM']
    #            #Вычисляем мощность нагрева
    #            power = pid(self.config['TEMP'])
    #            PWM = power*10 #Для ШИМ необходим диапазон от 0 до 1000, умножаем мощность на 10
    #            self.config['POWER'] = round(PWM)
    #            self.dprint('PWM in:', PWM, 'POWER out:', self.config['POWER'], 'POWER in %', str(round(self.config['POWER']/10))+'%')
    #        else:
    #            self.config['POWER'] = 0
    #            self.dprint('Heating OFF!!!')
    #        self.heat.duty(self.config['POWER'])
    #        await asyncio.sleep(57)


    #Индикация подключения WiFi
    async def _heartbeat(self):
        while True:
            if self.config['internet_outage'] == True:
                self.wifi_led(not self.wifi_led())      #Быстрое мигание, если соединение отсутствует
                await asyncio.sleep_ms(200)
            elif self.config['internet_outage'] == False:
                self.wifi_led(0)                        #Редкое мигание при подключении
                await asyncio.sleep_ms(50)
                self.wifi_led(1)
                await asyncio.sleep_ms(5000)
            else:
                self.wifi_led(0)                        #Два быстрых миганиения при AP Mode
                await asyncio.sleep_ms(50)
                self.wifi_led(1)
                await asyncio.sleep_ms(50)
                self.wifi_led(0)
                await asyncio.sleep_ms(50)
                self.wifi_led(1)
                await asyncio.sleep_ms(5000)


    ##Вычисление тарифной зоны день
    #sync def _calc_tariff_zone(self):
    #    while True:
    #        if self.config['RTC'].rtctime()[4] == 0: #Если минуты обнулились, прошел 1 час делаем проверку тарифной зоны
    #            delta = self.config['timezone']-self.tzone.adj_tzone(self.config['RTC'].rtctime())
    #            if delta == 1: #Если Зимняя тарифная зона вычитаем из часов delta
    #                self.config['DAY_ZONE'] = ((self.config['TARIFF_ZONE'][0][0]-delta,)\
    #                +self.config['TARIFF_ZONE'][0][1:]),\
    #                (self.config['TARIFF_ZONE'][1][0]-delta,)+self.config['TARIFF_ZONE'][1][1:]
    #            else: #Если Летняя тарифная зона, 'DAY_ZONE' = 'TARIFF_ZONE'
    #                self.config['DAY_ZONE'] = self.config['TARIFF_ZONE']
    #            await asyncio.sleep(60)
    #        await asyncio.sleep(1)


    #Сбор информации с температурных датчиков DS18D20
    async def _collection_temp(self):
        roms = self.ds.scan()
        while True:
            self.ds.convert_temp()
            await asyncio.sleep(2)
            self.config['TEMP'] = round(self.ds.read_temp(roms[0]) - 1.1 , 2)


    #Запуск WEB приложения
    async def _start_web_app(self):
        while True:
            gc.collect()                                    #Очищаем RAM
            await asyncio.sleep(5)
            if not self.config['internet_outage'] or self.config['internet_outage'] == 'AP':
                self.ip = self.config['WIFI'].ifconfig()[0]
                self.dprint('Run WebAPP...')
                app.run(debug=self.config['WEB_Debug'], host =self.ip, port=80)


    async def _run_main_loop(self):                         #Бесконечный цикл
        while True:
            self.config['MemFree'] = str(round(gc.mem_free()/1024, 2))
            self.config['MemAvailab'] = str(round(gc.mem_alloc()/1024, 2))
            self.config['FREQ'] = str(freq()/1000000)
            lt = self.config['RTC_TIME']
            wifi = 'connected' if not self.config['internet_outage'] else 'disconnected'
            gc.collect()                                    #Очищаем RAM
            try:
                self.dprint('################# DEBUG MESSAGE ##########################')
                self.dprint('Uptime:', str(self.config['Uptime'])+' min')
                self.dprint('WiFi:', wifi)
                self.dprint('IP:', self.config['IP'])
                self.dprint('Local Time:', '{:0>2d}-{:0>2d}-{:0>2d} {:0>2d}:{:0>2d}:{:0>2d}'\
                            .format(lt[0], lt[1], lt[2], lt[3], lt[4], lt[5]))
                self.dprint('DST:', bool_to_str(self.config['DST']))
                self.dprint('Heating:', bool_to_str(self.config['HEAT']))
                self.dprint('Power limit:', '{}%'.format(self.config['WEBPOWER']))
                self.dprint('Actual power:', '{}%'.format(str(round(self.config['POWER']/10))))
                self.dprint('Set:', '{}`C'.format(str(self.config['T_ROOM'])))
                self.dprint('Room:', '{}`C'.format(str(self.config['TEMP'])))
                self.dprint('MemFree:', '{}Kb'.format(self.config['MemFree']))
                self.dprint('MemAvailab:', '{}Kb'.format(self.config['MemAvailab']))
                self.dprint('FREQ:', '{}MHz'.format(self.config['FREQ']))
                self.dprint('################# DEBUG MESSAGE END ######################')
            except Exception as e:
                self.dprint('Exception occurred: ', e)
            self.config['Uptime'] += 1
            await asyncio.sleep(60)


    async def main(self):
        while True:
            try:
                await self.connect() #Включение WiFi и контроль соединения
                await self._run_main_loop()
            except Exception as e:
                self.dprint('Global communication failure: ', e)
                await asyncio.sleep(20)


gc.collect()                                                #Очищаем RAM
def_main = Main()
loop = asyncio.get_event_loop()
loop.run_until_complete(def_main.main())
