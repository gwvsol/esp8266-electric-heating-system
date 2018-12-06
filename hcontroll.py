import gc, network, os
import uasyncio as asyncio
gc.collect()                                #Очищаем RAM

config = {}                                 #Основное хранилище настроек

#Базовый класс
class HeatControlBase:
    DEBUG = False
    def __init__(self, config):
        self.config = config


    #Проверяем наличие файлов
    def exists(self, path):
        try:
            os.stat(path)
        except OSError:
            return False
        return True


    #Выводим отладочные сообщения
    def dprint(self, *args):
        if self.DEBUG:
            print(*args)


    def _con(self):
        if self.config['MODE_WiFi'] == 'AP':
            self.config['WIFI'].active(True)
            self.config['WIFI'].config(essid=self.config['ssid'], password=self.config['wf_pass'])
            # Configure the AP to static IPs
            self.config['WIFI'].ifconfig(self.config['WIFI_AP'])
        elif self.config['MODE_WiFi'] == 'ST':
            self.config['WIFI'].active(True)
            network.phy_mode(1) # network.phy_mode = MODE_11B
            self.config['WIFI'].connect(self.config['ssid'], self.config['wf_pass'])


    def _error_con(self):
        #Соединение не установлено...
        if self.config['WIFI'].status() == network.STAT_CONNECT_FAIL:
            self.dprint('WiFi: Failed due to other problems')
        #Соединение не установлено, причина не найдена точка доступа
        if self.config['WIFI'].status() == network.STAT_NO_AP_FOUND:
            self.dprint('WiFi: Failed because no access point replied')
        #Соединение не установлено, не верный пароль
        if self.config['WIFI'].status() == network.STAT_WRONG_PASSWORD:
            self.dprint('WiFi: Failed due to incorrect password')


    async def connect_wf(self):
        if self.config['MODE_WiFi'] == 'AP':
            self.dprint('WiFi AP Mode!')
            self._con()
            if self.config['WIFI'].status() == -1:
                self.dprint('WiFi: AP Mode OK!')
                self.config['IP'] = self.config['WIFI'].ifconfig()[0]
                self.dprint('WiFi:', self.config['IP'])
                self.config['internet_outage'] = 'AP'
        elif self.config['MODE_WiFi'] == 'ST':
            self.dprint('Connecting to WiFi...')
            self._con()
            if self.config['WIFI'].status() == network.STAT_CONNECTING:
                self.dprint('WiFi: Waiting for connection to...')
            # Задержка на соединение, если не успешно, будет выдана одна из ошибок
            # Выполнение условия проверяем каждую секунду, задержка для получения IP адреса от DHCP
            while self.config['WIFI'].status() == network.STAT_CONNECTING:
                await asyncio.sleep(1)
            #Соединение успешно установлено
            if self.config['WIFI'].status() == network.STAT_GOT_IP:
                self.dprint('WiFi: Connection successfully!')
                self.config['IP'] = self.config['WIFI'].ifconfig()[0]
                self.dprint('WiFi:', self.config['IP'])
                self.config['internet_outage'] = False
            if not self.config['WIFI'].isconnected():
                self.config['internet_outage'] = True
                self.dprint('WiFi: Connection unsuccessfully!')
            self._error_con()


    async def reconnect(self):
        self.dprint('Reconnecting to WiFi...')
        self.config['IP'] = self.config['WIFI'].ifconfig()[0]
        self.config['WIFI'].disconnect()
        await asyncio.sleep(1)
        self._con()
        while self.config['WIFI'].status() == network.STAT_CONNECTING:
            await asyncio.sleep_ms(20)
        if self.config['WIFI'].status() == network.STAT_GOT_IP:
            self.config['IP'] = self.config['WIFI'].ifconfig()[0]
            self.config['internet_outage'] = False
            self.dprint('WiFi: Reconnecting successfully!')
            self.dprint('WiFi:', self.config['IP'])
        self._error_con()
        if not self.config['WIFI'].isconnected():
            self.config['internet_outage'] = True
            self.dprint('WiFi: Reconnecting unsuccessfully!')
        await asyncio.sleep(1)


class HeatControl(HeatControlBase):
    def __init__(self):
        super().__init__(config)


    #Проверка соединения с Интернетом
    async def _check_wf(self):
        while True:
            if not self.config['internet_outage']:
                if self.config['WIFI'].status() == network.STAT_GOT_IP:
                    await asyncio.sleep(1)
                else:
                    await asyncio.sleep(1)
                    self.config['internet_outage'] = True
            else:
                await asyncio.sleep(1)
                await self.reconnect()
        await asyncio.sleep(1)
        gc.collect()                                                    #Очищаем RAM


    #Подключаемся к WiFi
    async def connect(self):
        await self.connect_wf()
        if self.config['MODE_WiFi'] == 'ST':
            loop = asyncio.get_event_loop()
            loop.create_task(self._check_wf())
        elif self.config['MODE_WiFi'] == 'AP':
            gc.collect()                                                #Очищаем RAM
    
