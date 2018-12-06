import machine
try:
    import utime as time
except:
    import time
import uasyncio as asyncio
from hcontroll import config
import gc
from timezone import TZONE

class DS3231(object):

    def __init__(self, i2c):
        self.i2c = i2c
        self.i2c_addr = config['RTC_DS3231']
        self.zone = config['timezone']
        self.dst = config['DST']
        self.stime = config['SOURCE_TIME']
        self.webtime = config['WEB_TIME']                #Начальное значение для времени передаваемого с веб интерфейса
        self.tzone = TZONE(self.zone)
        self.default_time =  (2000, 1, 1, 0, 0, 0, 0, 0) #Дефолтное время для сброса времени на RTC DS3231
        self.timebuf = bytearray(7)
        self.rtc = False # Изменяется на True только когда март или октябрь и только в последнее воскресенье месяца
        if self.i2c_addr in self.i2c.scan():
            print('RTS DS3231 find at address: 0x%x ' %(self.i2c_addr))
        else:
            print('RTS DS3231 not found at address: 0x%x ' %(self.i2c_addr))
        gc.collect()                                      #Очищаем RAM

        loop = asyncio.get_event_loop()
        loop.create_task(self._update_time())             #Включаем автоматическое обновление времени


    def _bcd2dec(self, bcd): # Преобразование двоично-десятичного формата
        return (((bcd & 0xf0) >> 4) * 10 + (bcd & 0x0f))

    
    def _dec2bcd(self, dec): # Преобразование в двоично-десятичный формат
        tens, units = divmod(dec, 10)
        return (tens << 4) + units


    def _tobytes(self, num):
        return num.to_bytes(1, 'little')
    

    def rtctime(self): # Считываем время с RTC DS3231
        self.i2c.readfrom_mem_into(self.i2c_addr, 0, self.timebuf)
        return self._convert()


    # Преобразуем время RTC DS3231 в формат esp8266
    # Возвращает кортеж в формате localtime()
    # (с днем недели уменьшеном на 1, так как в esp8266 0 - понедельник, а 6 - воскресенье)
    def _convert(self):
        data = self.timebuf
        ss = self._bcd2dec(data[0])
        mm = self._bcd2dec(data[1])
        if data[2] & 0x40:
            hh = self._bcd2dec(data[2] & 0x1f)
            if data[2] & 0x20:
               hh += 12
        else:
            hh = self._bcd2dec(data[2])
        wday = data[3]
        DD = self._bcd2dec(data[4])
        MM = self._bcd2dec(data[5] & 0x1f)
        YY = self._bcd2dec(data[6])
        if data[5] & 0x80:
            YY += 2000
        else:
            YY += 1900
        # Time from DS3231 in time.localtime() format (less yday)
        result = YY, MM, DD, hh, mm, ss, wday -1, 0 # wday-1 because in esp8266 0 == Monday, 6 == Sunday
        return result


    # Обновляем время RTC DS3231 по данным которые получаем с localtime (по умолчанию) 
    # при вызове метода с параметром False или с NTP сервера при доступности интернет соединения, 
    # если соединение не доступно, использует время RTC на DS3231 
    # при вызове метода с параметром True обнуляет часы до (2000, 1, 1, 0, 0, 0, 0, 0)
    def save_time(self, default=False):
        if  self.stime == 'local' and not default: # Используем локальное время микроконтроллера
            (YY, MM, mday, hh, mm, ss, wday, yday) = time.localtime() # Based on RTC
        elif self.stime == 'web' and not default:
            (YY, MM, mday, hh, mm, ss, wday, yday) = self.webtime #Время с веб интерфейса
        elif not default: # Используем время RTC или NTP сервера
            if self.stime == 'ntp' and not self.rtc:
                utc = time.localtime(self.tzone.getntp())
                z = self.tzone.adj_tzone(utc) if self.dst else 0
            elif self.rtc: # RTC время используется для перевода времени на летнее или зимнее время
                utc = self.rtctime()
                z = 1 if utc[1] == 3 else -1 # Если март перевод времени на час вперед, если октябрь на час назад
            (YY, MM, mday, hh, mm, ss, wday, yday) =  utc[0:3] + (utc[3]+z,) + utc[4:7] + (utc[7],)
        else: # При передаче параметра default=True время сбрасывается в (2000, 1, 1, 0, 0, 0, 0, 0)
            (YY, MM, mday, hh, mm, ss, wday, yday) = self.default_time
        # Записываем время в DS3231
        self.i2c.writeto_mem(self.i2c_addr, 0, self._tobytes(self._dec2bcd(ss)))
        self.i2c.writeto_mem(self.i2c_addr, 1, self._tobytes(self._dec2bcd(mm)))
        self.i2c.writeto_mem(self.i2c_addr, 2, self._tobytes(self._dec2bcd(hh)))  # Sets to 24hr mode
        self.i2c.writeto_mem(self.i2c_addr, 3, self._tobytes(self._dec2bcd(wday + 1)))  # because in ds3231 1 == Monday, 7 == Sunday
        self.i2c.writeto_mem(self.i2c_addr, 4, self._tobytes(self._dec2bcd(mday)))  # Day of month
        if YY >= 2000:
            self.i2c.writeto_mem(self.i2c_addr, 5, self._tobytes(self._dec2bcd(MM) | 0b10000000))  # Century bit
            self.i2c.writeto_mem(self.i2c_addr, 6, self._tobytes(self._dec2bcd(YY-2000)))
        else:
            self.i2c.writeto_mem(self.i2c_addr, 5, self._tobytes(self._dec2bcd(MM)))
            self.i2c.writeto_mem(self.i2c_addr, 6, self._tobytes(self._dec2bcd(YY-1900)))
        print('New RTC Time: ', self.rtctime()) # Выводим новое время DS3231
        
        
    # Основной асинхронный метод для автоматического обновления времени с NTP сервера  
    # или для перехода на летнее или зимнее время
    async def _update_time(self):
        while True:
            rtc = self.rtctime()
            if rtc[0] <= 2000:
                if self.tzone.getntp() > 0: # Если соединение
                    self.save_time()  # Обновляем время на DS3231
                    await asyncio.sleep(10)
            # Если март или октябрь
            if rtc[1] == 3 or rtc[1] == 10:
                rtc = self.rtctime()
                # Если время 3часа утра и последнее воскресенье месяца
                if rtc[3] == 3 and self.tzone.sunday(rtc[0], rtc[1]) == rtc[2]:
                    self.rtc = True
                    self.save_time() # Переводим время
                    self.rtc = False
                    if rtc[1] == 3: # Если март, задержка 60сек, т.к переводим вперед
                        await asyncio.sleep(60)
                    else: # Если октябрь, задержка 3660сек, т.к переводим назад
                        await asyncio.sleep(3660)
            gc.collect() #Очищаем RAM
            await asyncio.sleep(5)
