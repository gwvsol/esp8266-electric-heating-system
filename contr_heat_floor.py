from time import ticks_ms, ticks_diff, sleep_ms
from machine import I2C, Pin
from i2c_lcd_api import I2cLcd
from i2c_ds3231 import DS3231
import uasyncio as asyncio
import time, network, gc

i2c = I2C(scl=Pin(5), sda=Pin(4), freq=400000) # Настройка шины i2c

class ControlHeated(object):
    wifi_led = Pin(2, Pin.OUT, value = 1) #Настройка Pin2, к нему подключен светодиод на плате контроллера
    
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
        self.config['RTC_DS3231'] = 0x68 # Адрес DS3231 RTC
        self.config['LCD_lines'] = 4 # Количество строк LCD
        self.config['LCD_symbol'] = 20 # Количество символов в строке LCD
        self.config['DATE'] = '2000-00-00' #Начальные значения даты
        self.config['TIME'] = '00:00:00'      #Начальное значение времени
        self.config['SOURCE_TIME'] = 'ntp' # Где брать время для настройки часов DS3231
                                           # ntp - сервер NTP, local - часы контроллера
           
        loop = asyncio.get_event_loop()
        loop.create_task(self._heartbeat())
        loop.create_task(self._update_time())
        loop.create_task(self._display_information())
        loop.create_task(self._conversion_info())
        
        
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
                
                
    # Получение времени с сервера NTP и обноление по Time Zone
    async def _update_time(self):
        self.rtc = DS3231(i2c, self.config['RTC_DS3231'], self.config['timezone'], \
        self.config['win'], self.config['SOURCE_TIME'])
        while True:
            if self.rtc.rtctime()[0] <= 2000:
                if self.internet_outage: # Не всегда соединение в WiFi быстро
                    await asyncio.sleep(10) #Если нет соединения с интернетом, ожидаем 10с
                self.rtc.save_time()
            await asyncio.sleep(86400) # Проверка один раз в сутки

    
    #Выводим отладочные сообщения        
    def dprint(self, *args):
        if self.DEBUG:
            print(*args)
            
            
    #Конвертируем информацию для LCD
    async def _conversion_info(self):
        while True:
            tm = self.rtc.rtctime()
            year = str(tm[0])
            month = self.config['num'][tm[1]] if tm[1] < 10 else str(tm[1])
            day = self.config['num'][tm[2]] if tm[2] < 10 else str(tm[2])
            hr = self.config['num'][tm[3]] if tm[3] < 10 else str(tm[3])
            m = self.config['num'][tm[4]] if tm[4] < 10 else str(tm[4])
            s = self.config['num'][tm[5]] if tm[5] < 10 else str(tm[5])
            self.config['DATE'] = year+'-'+month+'-'+day
            self.config['TIME'] = hr+':'+m+':'+s
            await asyncio.sleep_ms(900)
            
    
    #Вывод информации на LCD HD44780 по шине i2c через PCF8574
    async def _display_information(self):
        lcd = I2cLcd(i2c, self.config['LCD_I2C_ADDR'], self.config['LCD_lines'], \
        self.config['LCD_symbol'])
        while True:
            lcd.move_to(1, 0) #Переходим на 1 символ 1 строки
            lcd.putstr(self.config['DATE'])  #Выводим дату
            lcd.move_to(12, 0) #Переходим на 14 символ 1 строки
            lcd.putstr(self.config['TIME'])   #Выводим время
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
            loctime = self.rtc.rtctime()
            try:
                self.dprint('Uptime:', str(mins)+' min')
                self.dprint('Local Time:', loctime)
                self.dprint('Not WiFi:', self.internet_outage)
                self.dprint('IP:', self.ip)
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

