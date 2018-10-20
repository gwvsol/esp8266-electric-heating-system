import machine
try:
   import utime as time
except:
   import time
import ntp

# time zones is supported
TIME_ZONE = {-11: -11, -10: -10, -9: -9, -8: -8, -7: -7, -6: -6, -5: -5, \
-4: -4, -3: -3, -2: -2, -1: -1, 0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, \
7: 7, 8: 8, 9: 9, 10: 10, 11: 11, 12: 12, 13: 13, 14: 14}
# months of summer and winter time
MONTH = {'sum': 3, 'win': 10} # 3 - march, 10 - october


#Calculate the last Sunday of the month
#https://ru.wikibooks.org/wiki/Реализации_алгоритмов/Вечный_календарь
def sunday(year, month):
    for d in range(1,32):
        a = (14 - month) // 12
        y = year - a
        m = month + 12 * a -2
        if (((d + y + y // 4 - y // 100 + y // 400 + (31 * m) // 12)) % 7) == 0: # 0 - Sunday
            if d + 7 > 31: 
                return d


#We calculate summer or winter time now
def adj_tzone(utc, zone):
    if utc[1] > MONTH['sum']:
        if utc[1] <= MONTH['win'] and utc[2] < sunday(utc[0], MONTH['win']):
            print('Set TIME ZONE Summer:', TIME_ZONE[zone])
            return TIME_ZONE[zone]
    if utc[1] == MONTH['sum'] and utc[2] >= sunday(utc[0], MONTH['sum']):
        print('Set TIME ZONE Summer:', TIME_ZONE[zone])
        return TIME_ZONE[zone]
    else:
        print('Set TIME ZONE Winter:', TIME_ZONE[zone] - 1)
        return TIME_ZONE[zone] - 1


# Adjustment time.localtime in accordance with time zones and changes for summer and winter time
# Not the entire list of time zones is supported
def setzone(tg=(2000, 0, 0, 0, 0, 0, 0, 0), zone=0, win=True): # По умолчанию включен переход на серзонное время
    #utc = (tg[0], 10, 27,) + tg[3:7] #Added for debugging code
    utc = tg
    #utc = time.localtime(ntp.getntp()) # The tuple in UTC, for example - (2018, 10, 11, 13, 56, 9, 3, 284)
    # We form a new cortege to upgrade from the time zone
    z = adj_tzone(utc, zone) if win else 0 # Проверяем включен ли переход на сезонное время
    nt = utc[0:3] + (0,) + (utc[3]+z,) + utc[4:6] + (0,)
    print('Update time for Time Zone: ', z)
    # We update the time taking into account the time zone and summer and winter time
    machine.RTC().datetime(nt)
    print('Local Time: ', str(time.localtime()))


def stime():
    setzone(time.localtime(ntp.getntp()))


