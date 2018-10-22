import machine
try:
    import utime as time
except:
    import time
try:
    import usocket as socket
except:
    import socket
try:
    import ustruct as struct
except:
    import struct
try:
    import uerrno as errno
except:
    import errno


class DS3231(object):

    def __init__(self, i2c, i2c_addr, zone=0, win=True, source_time='local'):
        self.i2c = i2c
        self.i2c_addr = i2c_addr
        self.timebuf = bytearray(7)
        self.zone = zone
        self.win = win
        self.stime = source_time
        if self.i2c_addr in self.i2c.scan():
            print('RTS DS3231 find at address: 0x%x ' %(self.i2c_addr))
        else:
            print('RTS DS3231 not found at address: 0x%x ' %(self.i2c_addr))
        # time zones is supported
        self.TIME_ZONE = {-11: -11, -10: -10, -9: -9, -8: -8, -7: -7, -6: -6, -5: -5, \
        -4: -4, -3: -3, -2: -2, -1: -1, 0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, \
        7: 7, 8: 8, 9: 9, 10: 10, 11: 11, 12: 12, 13: 13, 14: 14}
        # months of summer and winter time
        self.MONTH = {'sum': 3, 'win': 10} # 3 - march, 10 - october
        
        # (date(2000, 1, 1) - date(1900, 1, 1)).days * 24*60*60
        self.NTP_DELTA = 3155673600
        # NTP server
        self.host = "pool.ntp.org"


    # Преобразование двоично-десятичного формата
    def bcd2dec(self, bcd):
        return (((bcd & 0xf0) >> 4) * 10 + (bcd & 0x0f))


    # Преобразование в двоично-десятичный формат
    def dec2bcd(self, dec):
        tens, units = divmod(dec, 10)
        return (tens << 4) + units

    def tobytes(self, num):
        return num.to_bytes(1, 'little')
    
    #Обновление времени по NTP    
    def getntp(self):
        print('Get UTC time from NTP server...')
        NTP_QUERY = bytearray(48)
        NTP_QUERY[0] = 0x1b
       # Handling an unavailable NTP server error
        try:
            addr = socket.getaddrinfo(self.host, 123)[0][-1]
        except OSError: # as exc:
            #if exc.args[0] == -2:
                print('Connect NTP Server: Error resolving pool NTP')
                return 0
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        res = s.sendto(NTP_QUERY, addr)
       # Handling NTP server long response error
        try:
            msg = s.recv(48)
        except OSError as exc:
            if exc.args[0] == errno.ETIMEDOUT:
                print('Connect NTP Server: Request Timeout')
                s.close()
                return 0
        s.close()
        val = struct.unpack("!I", msg[40:44])[0]
        return val - self.NTP_DELTA

    #Calculate the last Sunday of the month
    #https://ru.wikibooks.org/wiki/Реализации_алгоритмов/Вечный_календарь
    def sunday(self, year, month):
        for d in range(1,32):
            a = (14 - month) // 12
            y = year - a
            m = month + 12 * a -2
            if (((d + y + y // 4 - y // 100 + y // 400 + (31 * m) // 12)) % 7) == 0: # 0 - Sunday
                if d + 7 > 31: 
                    return d
    
    
    # We calculate summer or winter time now
    # В качестве параметра utc необходимо передать кортедж вида: (2018, 10, 22, 13, 31, 25, 0, 295)
    def adj_tzone(self, utc, zone):
        # Если текущий месяц больше 3(март) 
        if utc[1] > self.MONTH['sum']:
            # Проверяем равен ли месяц 10(октябрь) или меньше 10 и меньше ли дата последнего воскресенья месяца
            if utc[1] <= self.MONTH['win'] and utc[2] < self.sunday(utc[0], self.MONTH['win']):
                print('Set TIME ZONE Summer:', self.TIME_ZONE[zone])
                return self.TIME_ZONE[zone] # Возращаем летнее время
        # Если месяц равен 3(март) проверяем больше ли дата последнего воскресенья месяца
        if utc[1] == self.MONTH['sum'] and utc[2] >= self.sunday(utc[0], self.MONTH['sum']):
            print('Set TIME ZONE Summer:', self.TIME_ZONE[zone])
            return self.TIME_ZONE[zone] # Возращаем летнее время
        else:
            print('Set TIME ZONE Winter:', self.TIME_ZONE[zone] - 1)
            return self.TIME_ZONE[zone] - 1 # Во всех остальных случаях возращаем зимнее время
            

    # Считываем время с RTC DS3231
    def rtctime(self):
        self.i2c.readfrom_mem_into(self.i2c_addr, 0, self.timebuf)
        return self.convert()


    # Преобразуем время RTC DS3231 в формат esp8266
    # Возвращает кортеж в формате localtime()
    # (с днем недели уменьшеном на 1, так как в esp8266 0 - понедельник, а 6 - воскресенье)
    def convert(self):
        data = self.timebuf
        ss = self.bcd2dec(data[0])
        mm = self.bcd2dec(data[1])
        if data[2] & 0x40:
            hh = self.bcd2dec(data[2] & 0x1f)
            if data[2] & 0x20:
               hh += 12
        else:
            hh = self.bcd2dec(data[2])
        wday = data[3]
        DD = self.bcd2dec(data[4])
        MM = self.bcd2dec(data[5] & 0x1f)
        YY = self.bcd2dec(data[6])
        if data[5] & 0x80:
            YY += 2000
        else:
            YY += 1900
        # Time from DS3231 in time.localtime() format (less yday)
        result = YY, MM, DD, hh, mm, ss, wday -1, 0 # wday-1 because in esp8266 0 == Monday, 6 == Sunday
        return result


    # Обновляем время RTC DS3231 по данным которые получаем или с localtime(по умолчанию) 
    # или с timezone.setzone при подключенной библиотеке timezone, 
    # при вызове функции с параметром True обнуляет часы до (2000, 0, 0, 0, 0, 0, 0, 0)
    def save_time(self, default=False):
        if  self.stime == 'local' and not default: # Используем локальное время микроконтроллера
            (YY, MM, mday, hh, mm, ss, wday, yday) = time.localtime() # Based on RTC
        elif self.stime == 'ntp' and not default: # Используем время NTP сервера
            utc = time.localtime(self.getntp())
            z = self.adj_tzone(utc, self.zone) if self.win else 0
            (YY, MM, mday, hh, mm, ss, wday, yday) =  utc[0:3] + (utc[3]+z,) + utc[4:7] + (utc[7],)
        else: # При передаче параметра default=True время сбрасывается в (2000, 0, 0, 0, 0, 0, 0, 0)
            (YY, MM, mday, hh, mm, ss, wday, yday) = (2000, 0, 0, 0, 0, 0, 0, 0)
        # Записываем время в DS3231
        self.i2c.writeto_mem(self.i2c_addr, 0, self.tobytes(self.dec2bcd(ss)))
        self.i2c.writeto_mem(self.i2c_addr, 1, self.tobytes(self.dec2bcd(mm)))
        self.i2c.writeto_mem(self.i2c_addr, 2, self.tobytes(self.dec2bcd(hh)))  # Sets to 24hr mode
        self.i2c.writeto_mem(self.i2c_addr, 3, self.tobytes(self.dec2bcd(wday + 1)))  # because in ds3231 1 == Monday, 7 == Sunday
        self.i2c.writeto_mem(self.i2c_addr, 4, self.tobytes(self.dec2bcd(mday)))  # Day of month
        if YY >= 2000:
            self.i2c.writeto_mem(self.i2c_addr, 5, self.tobytes(self.dec2bcd(MM) | 0b10000000))  # Century bit
            self.i2c.writeto_mem(self.i2c_addr, 6, self.tobytes(self.dec2bcd(YY-2000)))
        else:
            self.i2c.writeto_mem(self.i2c_addr, 5, self.tobytes(self.dec2bcd(MM)))
            self.i2c.writeto_mem(self.i2c_addr, 6, self.tobytes(self.dec2bcd(YY-1900)))
        print('New RTC Time: ', self.rtctime()) # Выводим новое время DS3231


    # Wait until DS3231 seconds value changes before reading and returning data
    def await_transition(self):
        self.i2c.readfrom_mem_into(self.i2c_addr, 0, self.timebuf)
        ss = self.timebuf[0]
        while ss == self.timebuf[0]:
            self.i2c.readfrom_mem_into(self.i2c_addr, 0, self.timebuf)
        return self.timebuf
        

    # Test hardware RTC against DS3231. Default runtime 10 min. Return amount
    # by which DS3231 clock leads RTC in PPM or seconds per year.
    # Precision is achieved by starting and ending the measurement on DS3231
    # one-seond boundaries and using ticks_ms() to time the RTC.
    # For a 10 minute measurement +-1ms corresponds to 1.7ppm or 53s/yr. Longer
    # runtimes improve this, but the DS3231 is "only" good for +-2ppm over 0-40C.
    def rtc_test(self, runtime=600, ppm=False):
        factor = 1000000 if ppm else 31557600  # seconds per year
        self.await_transition()  # Start on transition
        rtc_start = time.ticks_ms()  # and get RTC time NOW
        ds3231_start = time.mktime(self.convert())
        time.sleep(runtime)  # Wait a while (precision doesn't matter)
        self.await_transition()
        d_rtc = time.ticks_diff(time.ticks_ms(), rtc_start)
        d_ds3231 = 1000 * (time.mktime(self.convert()) - ds3231_start)
        return (d_ds3231 - d_rtc) * factor / d_ds3231
        
        
#from machine import I2C, Pin
#import time
#from i2c_ds3231 import DS3231
#i2c = I2C(scl=Pin(5), sda=Pin(4), freq=400000)
#rtc = DS3231(i2c, 0x68, 3, True, 'ntp')
#rtc.save_time(True)
#rtc.rtctime()
#time.localtime()
        
