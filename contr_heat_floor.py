from time import ticks_ms, ticks_diff, sleep_ms
from machine import I2C, Pin, PWM
from i2c_lcd_api import I2cLcd
from i2c_ds3231 import DS3231
import uasyncio as asyncio
import time, network, gc, onewire, ds18b20

i2c = I2C(scl=Pin(5), sda=Pin(4), freq=400000) # Настройка шины i2c

class ControlHeated(object):
    wifi_led = Pin(2, Pin.OUT, value = 1) #Pin2, светодиод на плате контроллера
    heat = PWM(Pin(12), freq=1000, duty=0)    #Pin12, управление нагревом пола
    lcd_on = Pin(14, Pin.IN)              #Pin14, кнопка включения LCD
    
    
    def __init__(self):
        # Основное хранилище настроек
        self.config = {}
        self.internet_outage = True #Интернет отключен(значение True)
        #Читаем из файла настройки WiFi и Временную зону и перевод времени с Летнего на Зимнее
        with open('config.txt') as conf_file:
            self.config['ssid'] = conf_file.readline().rstrip()
            self.config['wf_pass'] = conf_file.readline().rstrip()
            self.config['timezone'] = int(conf_file.readline().rstrip())
            self.config['win'] = conf_file.readline().rstrip()
        # Числа для часов от 0 до 9 с добавлением 0 для часов
        self.config['num'] = ('00', '01', '02', '03', '04', '05', '06', '07', '08', '09')
        self.config['LCD_I2C_ADDR'] = 0x27 # Адрес PCF8574 LCD
        self.config['RTC_DS3231'] = 0x68   # Адрес DS3231 RTC
        self.config['LCD_lines'] = 4       # Количество строк LCD
        self.config['LCD_symbol'] = 20     # Количество символов в строке LCD
        self.config['DATE'] = '2000-00-00' # Начальные значения даты
        self.config['TIME'] = '00:00:00'   # Начальное значение времени
        self.config['SOURCE_TIME'] = 'ntp' # Настройка DS3231, ntp - сервер NTP, local - часы MK
        self.config['TEMP'] = [20.00, 20.00] # Начальный массив данных о темратуре[0]-Heat[1]-Room
        self.config['ROOM'] = 22.7           # Температура в помещении при которой включиться отопление
        self.config['HEAT_MAX'] = 55       # Максимальная температура нагревателя отопления
        self.config['LCD_ON'] = True       # По умолчанию, при включении LCD включен
        self.config['DUTY'] = [0, 24, 96, 206, 345, 500, 654, 793, 904, 975, 1023]
        self.config['POWER'] = 0
        self.rtc = DS3231(i2c, self.config['RTC_DS3231'], self.config['timezone'], \
            self.config['win'], self.config['SOURCE_TIME']) # Включаем автоматическую работу с модулем RTC DS3231
           
        loop = asyncio.get_event_loop()
        loop.create_task(self._heartbeat()) # Индикация подключения WiFi
        loop.create_task(self._display_information()) #Вывод информации на LCD HD44780 по шине i2c через PCF8574
        loop.create_task(self._conversion_info()) #Конвертируем информацию для LCD
        loop.create_task(self._lcd_on()) #Проверяем нажата ли кнопка ключения LCD
        loop.create_task(self._collection_temp()) # Сбор информации с температурных датчиков DS18D20
        loop.create_task(self._heat_on_off()) # Управление отоплением
        loop.create_task(self._heat_logical()) # Логика управления отоплением
        
        
    # Включение LCD на 15 секунд
    async def _lcd_on(self):
        while True:
            await asyncio.sleep(15) #В момент включения, LCD работает 15с, затем выключается
            while self.lcd_on():
                self.config['LCD_ON'] = False
                await asyncio.sleep_ms(20) #Проверяем каждые 20ms нажатали кнопка
            self.config['LCD_ON'] = True
            
    #Управление отоплением
    async def _heat_on_off(self):
        while True:
            self.heat.duty(self.config['DUTY'][self.config['POWER']])
            await asyncio.sleep(1)
            
    #Логика управления отоплением
    async def _heat_logical(self):
        while True:
            await asyncio.sleep(2)
            # Выполняется, если не превышена максимальная температура нагревателя self.config['HEAT_MAX']
            while self.config['TEMP'][0] <  self.config['HEAT_MAX']:
                await asyncio.sleep(1)
                print('Room:', str(self.config['TEMP'][1]))
                # Если температура в помещении меньше чем self.config['ROOM'] включаем нагрев
                if self.config['TEMP'][1] < self.config['ROOM']:
                    print('Heat:', str(self.config['TEMP'][0]))
                    self.config['POWER'] = 1
                else: 
                    self.config['POWER'] = 0
                    await asyncio.sleep(1)
            self.config['POWER'] = 0 # Превышена максимальная температура выключаем нагрев    
            
        
    # Индикация подключения WiFi
    async def _heartbeat(self):
        while True:
            if self.internet_outage:
                self.wifi_led(not self.wifi_led()) # Быстрое мигание, если соединение отсутствует
                await asyncio.sleep_ms(200) 
            else:
                self.wifi_led(0) # Редкое мигание при подключении
                await asyncio.sleep_ms(50)
                self.wifi_led(1)
                await asyncio.sleep_ms(5000)
                
                
    # Сбор информации с температурных датчиков DS18D20
    async def _collection_temp(self):
        ds = ds18b20.DS18X20(onewire.OneWire(Pin(0))) # Set Temperature sensors
        roms = ds.scan()
        while True:
            ds.convert_temp()
            await asyncio.sleep(2)
            self.config['TEMP'] = [round(ds.read_temp(rom) - 1.3, 2) for rom in roms]
                
    
    #Выводим отладочные сообщения        
    def dprint(self, *args):
        if self.DEBUG:
            print(*args)
            
            
    #Конвертируем информацию о времени для LCD
    async def _conversion_info(self):
        while True:
            if self.config['LCD_ON']: #Если нужна информация на LCD, начинаем преобразование времени
                tm = self.rtc.rtctime()
                year = str(tm[0])
                month = self.config['num'][tm[1]] if tm[1] < 10 else str(tm[1])
                day = self.config['num'][tm[2]] if tm[2] < 10 else str(tm[2])
                hr = self.config['num'][tm[3]] if tm[3] < 10 else str(tm[3])
                m = self.config['num'][tm[4]] if tm[4] < 10 else str(tm[4])
                s = self.config['num'][tm[5]] if tm[5] < 10 else str(tm[5])
                self.config['DATE'] = year+'-'+month+'-'+day
                self.config['TIME'] = hr+':'+m+':'+s
                await asyncio.sleep_ms(800)
            else:
                await asyncio.sleep_ms(800)
            
    
    #Вывод информации на LCD HD44780 по шине i2c через PCF8574
    async def _display_information(self):
        lcd = I2cLcd(i2c, self.config['LCD_I2C_ADDR'], self.config['LCD_lines'], \
        self.config['LCD_symbol'])
        while True:
            if self.config['LCD_ON']: #Если нажата кнопка включаем LCD
                lcd.backlight_on()
                lcd.display_on()
                lcd.move_to(0, 0) #Переходим на 1 символ 1 строки
                lcd.putstr(self.config['DATE'])  #Выводим дату
                lcd.move_to(12, 0) #Переходим на 14 символ 1 строки
                lcd.putstr(self.config['TIME'])   #Выводим время
                lcd.move_to(0, 1)
                lcd.putstr('Room:')
                lcd.move_to(0, 2) #Выводим температуру в помещении
                lcd.putstr(str(self.config['TEMP'][1]))
                lcd.move_to(6, 1)
                lcd.putstr('Heat:')
                lcd.move_to(6, 2) #Выводим темературу нагревателя
                lcd.putstr(str(self.config['TEMP'][0]))
                lcd.move_to(13, 1)
                lcd.putstr('Power:')
                lcd.move_to(14, 2) #Выводим мощность нагрева
                lcd.putstr(str(self.config['POWER'])+'0%')
                await asyncio.sleep_ms(900)
            else: # В противном случае экран выключен
                lcd.display_off()
                lcd.backlight_off()
                await asyncio.sleep_ms(900)
            
            
    #Подключаемся к WiFi
    async def _connect_to_WiFi(self):
        self.dprint('Connecting to WiFi...')
        sta_if = network.WLAN(network.STA_IF)
        sta_if.active(True)
        sta_if.connect(self.config['ssid'], self.config['wf_pass'])
        self.dprint('Connected!')
        await asyncio.sleep(5)
        self.ip = sta_if.ifconfig()[0]
        self.internet_outage = False #Интернет подключен(значение False)
        

    async def _run_main_loop(self): #Бесконечный цикл
        mins = 0
        while True:
            gc.collect() #Очищаем RAM
            mem_free = gc.mem_free()
            mem_alloc = gc.mem_alloc()
            loctime = self.rtc.rtctime()[0:7]
            try:
                self.dprint('Uptime:', str(mins)+' min')
                self.dprint('Local Time:', loctime)
                self.dprint('Not WiFi:', self.internet_outage)
                self.dprint('IP:', self.ip)
                self.dprint('Temp Room:', str(self.config['TEMP'][1]))
                self.dprint('Temp Heat:', str(self.config['TEMP'][0]))
                self.dprint('MemFree:', str(round(mem_free/1024, 2))+' Kb')
                self.dprint('MemAlloc:', str(round(mem_alloc/1024, 2))+' Kb')
            except Extension as e:
                self.dprint('Exception occurred: ', e)
            mins += 1
            await asyncio.sleep(60)

           
    async def main(self):
         while True:
             try:
                 await self._connect_to_WiFi()
                 await self._run_main_loop()    
             except Exception as e:
                 self.dprint('Global communication failure: ', e)
                 await asyncio.sleep(20)
                 
                              
ControlHeated.DEBUG = True	# Режим отладки, делаем программу разговорчивой
        
gc.collect() #Очищаем RAM
controll = ControlHeated()
loop = asyncio.get_event_loop()
loop.run_until_complete(controll.main())

