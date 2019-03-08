from network import WLAN, AP_IF, STA_IF
from onewire import OneWire
from ds18b20 import DS18X20
from machine import I2C, Pin, PWM
from time import mktime
import uasyncio as asyncio
from gc import collect, mem_free, mem_alloc
from i2c_ds3231 import DS3231
from timezone import TZONE
from esp_pid import PID
from hcontroll import HeatControl, read_write_root, read_write_config, update_config
from webapp import app
collect()                                                               # Очищаем RAM

class Main(HeatControl):
    def __init__(self):
        super().__init__()
        self.wifi_led = Pin(2, Pin.OUT, value = 1)                # Pin2, светодиод на плате контроллера
        self.heat = PWM(Pin(13), freq=1000, duty=0)                # Pin12, управление нагревом пола
        self.default_on = Pin(14, Pin.IN)                          # Pin14, кнопка для сброса настроек в дефолт
        self.i2c = I2C(scl=Pin(5), sda=Pin(4), freq=400000)     # Настройка шины i2c
        self.ds = DS18X20(OneWire(Pin(12)))        # Set Temperature sensors
        # Дефолтные настройки, если файла config.txt не будет обнаружено в системе
        self.default = {}
        self.default['MODE'] = 'AP'         # Включаем точку доступа
        self.default['ssid'] = 'HEAT_CONTROL'    # Устанавливаем имя точки доступа
        self.default['pass'] = 'roottoor'        # Пароль для точки доступа
        self.default['timezone'] = 3             # Временная зона
        self.default['DST'] = True               # Разрешаем переход с летнего на зимнее время
        self.default['SET'] = 20.0               # Установка поддерживаемой температуры в помещении
        self.default['DAY'] = 50                 # Уменьшение мощности в дневное время в %
        self.default['ON'] = (0, 0, 0, 22, 0, 0, 0, 0)     # Время включения обогрева 20:00
        self.default['OFF'] = (0, 0, 0, 8, 0, 0, 0, 0)     # Время выключения обогрева 08:00
        self.default['WORK'] = 'ON'              # Постоянный обогрев включен
        self.default['DS_K'] = -5.0              # Поправочный коэффициент для DS18B20
        # Дефолтный хещ логин, пароль для web admin (root:root)
        self.default_web = str(b'0242c0436daa4c241ca8a793764b7dfb50c223121bb844cf49be670a3af4dd18')
        # Основные настройки системы
        self.config['DEBUG'] = False             # Режим отладки, делаем программу разговорчивой
        self.config['RTC_DS3231'] = 0x68         # Адрес DS3231 RTC
        self.config['WIFI_AP'] = ('192.168.4.1', '255.255.255.0', '192.168.4.1', '208.67.222.222')
        self.config['TARIFF_ZONE'] = ((7, 0, 0), (22, 59, 59)) # Тарифнаф зона день с 7 до 22:59
        self.config['DAY_ZONE'] = ((7, 0, 0), (22, 59, 59))    # Дефолтное значение тарифной зоны день
        self.config['TEMP'] = 18.00          # Начальное значение темратуры в помещении
        self.config['DUTY_MIN'] = 0          # Режим работы ПИД регулятора, минимальный предел
        self.config['DUTY_MAX'] = 90         # Режим работы ПИД регулятора, максимальный предел, установлен в 90% 
                                             # для исключения перегрева нагревателя
        self.config['RTC_TIME'] = (0, 1, 1, 0, 0, 0, 0, 0)  # Дефолтное время
        self.config['PID_KP'] = 5
        self.config['PID_KI'] = 0.1
        self.config['PID_KD'] = 0.01
        self.config['SETPOWER'] = 0             # Заданное значение мощности нагревателя
        self.config['POWER'] = 0                # Начальное значение мощности нагревателя
        self.config['NTP_UPDATE'] = True        # Разрешаем обновление по NTP
        self.config['IP'] = None                # Дефолтный IP адрес
        self.config['no_wifi'] = True           # Интернет отключен(значение True)
        # Eсли файла config.txt не обнаружено в системе создаем его
        if self.exists('config.txt') == False or not self.default_on():
            read_write_config(cfg=self.default)
        # Eсли файла root.txt нет создаем его
        if self.exists('root.txt') == False or not self.default_on():
            read_write_root(passwd=self.default_web)
        # Читаем настройки из файла config.txt
        update_config()
        # Начальные настройки сети AP или ST
        if self.config['MODE'] == 'AP':
            self._ap_if = WLAN(AP_IF)
            self.config['WIFI'] = self._ap_if
        elif self.config['MODE'] == 'ST':
            self._sta_if = WLAN(STA_IF)
            self.config['WIFI'] = self._sta_if
        # Настройка для работы с RTC
        self.config['RTC']= DS3231(self.i2c, \
                    self.config['RTC_DS3231'], self.config['timezone'], ) #В ключаем работу с модулем RTC DS3231
        self.rtc = self.config['RTC']
        self.config['NOW'] = mktime(self.rtc.datetime())
        # Включаем поддержку TIME ZONE
        self.tzone = TZONE(self.config['timezone'])     

        loop = asyncio.get_event_loop()
        loop.create_task(self._heartbeat())              # Индикация подключения WiFi
        loop.create_task(self._collection_temp())        # Сбор информации с температурных датчиков DS18D20 и Вычисление тарифных зон
        loop.create_task(self._dataupdate())             # Обновление информации и часы
        loop.create_task(self._start_web_app())          # Включаем WEB приложение
        collect()                                                       #Очищаем RAM


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
            if self.config['MODE'] == 'ST' and not self.config['no_wifi']:
                # Подводка часов по NTP каждые сутки в 22:00:00
                if rtc[3] == 22 and rtc[4] == 5 and rtc[5] < 3 and self.config['NTP_UPDATE']:
                        self.config['NTP_UPDATE'] = False
                        self.rtc.settime('ntp')
                        await asyncio.sleep(1)
                        self.config['NTP_UPDATE'] = True
            collect()                                                   #Очищаем RAM
            await asyncio.sleep(1)


    #Индикация подключения WiFi
    async def _heartbeat(self):
        while True:
            if self.config['no_wifi'] == True:
                self.wifi_led(not self.wifi_led())      #Быстрое мигание, если соединение отсутствует
                await asyncio.sleep_ms(200)
            elif self.config['no_wifi'] == False:
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


    # Сбор данных с DS18D20, Вычисление тарифной зоны день, Управление отоплением и логикой работы отопления
    async def _collection_temp(self):
        roms = self.ds.scan()
        #Создаем ПИД регулятор
        pid = PID(self.config['PID_KP'], self.config['PID_KI'], self.config['PID_KD'], setpoint=self.config['SET'])
        #Устанавливаем минимальный и максимальный предел работы регулятора
        pid.output_limits = (self.config['DUTY_MIN'], self.config['DUTY_MAX'])
        #Устанавливаем поддерживаемую температуру
        t_room = self.config['SET']
        heat = False
        while True:
            rtc = self.config['RTC_TIME']
    # Вычисление тарифной зоны день, если минуты обнулились, прошел 1 час делаем проверку тарифной зоны
            if self.config['RTC_TIME'][4] == 0 and self.config['RTC_TIME'][5] < 10:
                delta = self.config['timezone']-self.tzone.adj_tzone(self.config['RTC_TIME'])
                if delta == 1: #Если Зимняя тарифная зона вычитаем из часов delta
                    self.config['DAY_ZONE'] = ((self.config['TARIFF_ZONE'][0][0]-delta,)\
                    +self.config['TARIFF_ZONE'][0][1:]),\
                    (self.config['TARIFF_ZONE'][1][0]-delta,)+self.config['TARIFF_ZONE'][1][1:]
                else: #Если Летняя тарифная зона, 'DAY_ZONE' = 'TARIFF_ZONE'
                    self.config['DAY_ZONE'] = self.config['TARIFF_ZONE']
    # Считываем показания с датчика температуры
            self.ds.convert_temp()
            await asyncio.sleep(2)
            self.config['TEMP'] = round(self.ds.read_temp(roms[0]) + self.default['DS_K'] , 2)
    #Логика управления отоплением
            st = self.config['DAY_ZONE'][0]
            end = self.config['DAY_ZONE'][1]
            st = mktime((rtc[0], rtc[1], rtc[2], st[0], 0, 0, 0, 0))
            end = mktime((rtc[0], rtc[1], rtc[2], end[0], end[1], end[2], 0, 0))
            # Если тариф дневной зоны, ограничиваем мощность нагрева на self.config['DAY']%
            if st < self.config['NOW'] and self.config['NOW'] < end:
                pid.output_limits = (self.config['DUTY_MIN'], self.config['DAY'])
                self.config['SETPOWER'] = self.config['DAY']
            else: # Если тариф ночной зоны, разрешаем нагрев до self.config['DUTY_MAX']%
                pid.output_limits = (self.config['DUTY_MIN'], self.config['DUTY_MAX'])
                self.config['SETPOWER'] = self.config['DUTY_MAX']
            if t_room != self.config['SET']:
                pid.set_setpoint = self.config['SET']
                t_room = self.config['SET']
    # Вычисляем мощность нагрева
            if heat:
                self.config['POWER'] = round(pid(self.config['TEMP'])*10) # Для ШИМ необходим диапазон от 0 до 1000, умножаем мощность на 10
            else:
                self.config['POWER'] = 0
            self.heat.duty(self.config['POWER'])
    # Обрабатываем режимы работы контроллера
            if self.config['WORK'] == 'ON': # Режим поддержания температуры
                heat = True
            elif self.config['WORK'] == 'TAB': # Режим работы по рассписанию
                on = self.config['ON']
                off = self.config['OFF']
                d = rtc[2] + 1 if int(on[3]) > int(off[3]) else rtc[2]
                on = mktime((rtc[0], rtc[1], rtc[2], on[3], on[4], 0, 0, 0))
                off = mktime((rtc[0], rtc[1], d, off[3], off[4], 0, 0, 0))
                if self.config['NOW'] > on and self.config['NOW'] < off:
                    heat = True
                else: heat = False
            elif self.config['WORK'] == 'OFF': # Обогрев выключен
                heat = False
            else: heat = False
            collect()                                                   #Очищаем RAM
            await asyncio.sleep(10)


    #Запуск WEB приложения
    async def _start_web_app(self):
        while True:
            await asyncio.sleep(5)
            if not self.config['no_wifi'] or self.config['MODE'] == 'AP':
                self.ip = self.config['WIFI'].ifconfig()[0]
                self.dprint('Run WebAPP...')
                app.run(debug=self.config['DEBUG'], host =self.ip, port=80)


    async def _run_main_loop(self):                                     # Бесконечный цикл
        while True:
            #lt = self.config['RTC_TIME']
            #try:
            #    self.dprint('IP:', self.config['IP'])
            #    self.dprint('Local Time:', '{:0>2d}-{:0>2d}-{:0>2d} {:0>2d}:{:0>2d}:{:0>2d}'\
            #                          .format(lt[0], lt[1], lt[2], lt[3], lt[4], lt[5]))
            #    self.dprint('MemFree:', '{}Kb'.format(str(round(mem_free()/1024, 2))))
            #    self.dprint('MemAvailab:', '{}Kb'.format(str(round(mem_alloc()/1024, 2))))
            #except Exception as e:
            #    self.dprint('Exception occurred: ', e)
            collect()                                                   # Очищаем RAM
            await asyncio.sleep(30)


    async def main(self):
        while True:
            try:
                await self.connect() #Включение WiFi и контроль соединения
                await self._run_main_loop()
            except Exception as e:
                self.dprint('Global communication failure: ', e)
                await asyncio.sleep(20)


collect()                                                               #Очищаем RAM
def_main = Main()
loop = asyncio.get_event_loop()
loop.run_until_complete(def_main.main())
