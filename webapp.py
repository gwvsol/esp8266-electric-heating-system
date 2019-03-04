import picoweb, gc, ubinascii, json
from hcontroll import config
from ubinascii import hexlify
from uhashlib import sha256

app = picoweb.WebApp(__name__)

http_head = """<!DOCTYPE html>
        <html>
        <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width" initial-scale="1.0" maximum-scale="1.0" minimum-scale="1.0"/>
        <title>Heating System</title>
        <style> 
        html { font-family: 'Lato', Calibri, Arial, sans-serif;
               height: 100%; }
        body { background: #ddd;
            color: #333; }
        .header { width: 100%;
            padding-top: .7em;
            padding-bottom: .7em;
            float: left;
            font-size: 1.3em;
            font-weight: 400;
            text-align: center; }
        .info { margin:0 auto;
                width:200px; }
        .menu { width: 100%;
            float: left;
            font-size: 1em;
            font-weight: 400;
            text-align: center; }
        .admin { margin: 0 auto;
                 width: 350px; }
        .footer { width: 100%;
            padding-top: 2em;
            padding-bottom: 2em;
            float: left;
            font-size: .5em;
            font-weight: 400;
            text-align: center; }
        a { text-decoration: none; }
        a:link { color: #333; }
        a:visited { color: #333; }
        a:hover { color: #333; }
        a:active { color: #333; }
        a.login { font-size: 1em; }
        </style>
        </head>
        <body>
        <h2><a class="menu" href="/">HOME</a></h2> """
        
href_adm_panel = '<a class="login" href="admin">ADMIN PANEL</a>'
div_cl_header = '<div class="header">'
div_cl_info = '<div class="info">'
div_cl_admin = '<div class = "admin">'
div_end = '</div>'
span_err_pasw = '<span>Error Login<br>Close the browser, restart it,<br>and then try to log in again</span>'
mode_temp_power = """<form action='admin' method='POST'>
                <fieldset>
                    <legend>Mode, Power, Temperature, Time work</legend>
                    <p><input type="number" name="temp" size="4" min="15.0" max="30.0" step="0.1" value="20.0">'C Temperature<br>
                        <input type="number" name="power" size="4" min="10" max="90" step="5" value="50">% Daytime power limit</p>
                    <p><input type="radio" name="work_mode" checked value="contin">Continuous work<br>
                        <input type="radio" name="work_mode" value="schedule">On schedule<br>
                        <input type="radio" name="work_mode" value="offall">Turn off heating</p>
                    <p>Time<br>
                        <input type="time" name="time_on" required>On<br>
                        <input type="time" name="time_off" required>Off<br></p>
                    <p><input type="submit" value="Set control"></p>
                </fieldset>
            </form>"""
date_set = """<form action='admin' method='POST'>
                <fieldset>
                    <legend>Date and Time</legend>
                    <p>Daylight saving time<br>
                       <input type="radio" name="daylight" checked value="True">ON<br>
                       <input type="radio" name="daylight" value="False">OFF</p>
                    <p>Time on NTP server<br>
                        <input type="radio" name="ntp" checked value="True">ON<br>
                        <input type="radio" name="ntp" value="False">OFF</p>
                    <p><select size="1" name="tzone" required>
                       <option value="0">UTC +00:00</option>
                       <option value="1">UTC +01:00</option>
                       <option value="2">UTC +02:00</option>
                       <option value="3">UTC +03:00</option>
                       <option value="4">UTC +04:00</option>
                       </select></p>
                    <fieldset>
                        <legend>Setting time without an NTP server</legend>
                        <p><input type="date" name="date" required><br>
                           <input type="time" name="time" required></p>
                    </fieldset>
                    <p><input type="submit" value="Set Date&Time"></p>
                </fieldset>
            </form>"""
wifi_form = """<form action='admin' method='POST'>
                    <fieldset>
                        <legend>WiFi</legend>
                        <p><input type="radio" name="wifi" value="AP">AP<br>
                           <input type="radio" name="wifi" value="ST" checked>STATION</p>
                        <p><input type="text" name="ssid" placeholder="SSID" required autocomplete="off"><br>
                            <input type="password" name="pasw" pattern=".{8,12}" required title="8 to 12 characters" placeholder="WiFi Password" required autocomplete="off"><br>
                        <p><input type="submit" value="Set WiFi"></p>
                    </fieldset>
               </form>"""
passw_form = """<form action='admin' method='POST'>
                    <fieldset>
                        <legend>Password</legend>
                        <p><input type="text" name="login" required placeholder="Login" autocomplete="off"><br>
                            <input type="password" name="passw" pattern=".{8,12}" required title="8 to 12 characters" required placeholder="Password" autocomplete="off"><br>
                            <input type="password" name="repassw" pattern=".{8,12}" required title="8 to 12 characters" required placeholder="Repeat Password" autocomplete="off"></p>
                        <p><input type="submit" value="Сhange password"></p>
                    </fieldset>
                </form>"""
http_footer = """</body>
                <footer class="footer">
                    &copy; 2019, <a href="https://www.facebook.com/Syslighstar" target="_blank">SYSLIGHSTAR</a>
                </footer>
            </html>"""


def read_write_root(passwd=None):
    if passwd:
        print('Create new root.txt file')
        with open('root.txt', 'w') as f:
            f.write(passwd)
    else:
        with open('root.txt') as f:
            return f.readline().rstrip()


def read_write_config(cfg=None):
    if cfg:
        print('Create new config.txt file')
        with open('config.txt', 'w') as f:
            json.dump(cfg, f)
    else:
        with open('config.txt', 'r') as f:
            return json.loads(f.read())


def setpasswd(login, passwd):
    return str(hexlify(sha256(str(passwd+login).encode()).digest()))


def setroot(login, passw):
    passwd = setpasswd(login, passw)
    read_write_root(passwd=passw)
    if read_write_root() == passwd:
        return True
    else:
        return False


def str_to_bool(s):
    if s == 'True':
         return True
    elif s == 'False':
         return False
    else:
         raise ValueError


def bool_to_str(s):
    if s == True:
        return 'ON'
    elif s == False:
        return 'OFF'


def datetime_update(ntp, data, ntime):
    if str_to_bool(ntp):
        config['NTP_UPDATE'] = False
        config['RTC'].set_zone = config['timezone']
        config['RTC'].settime('ntp')
        config['NTP_UPDATE'] = True
    elif not str_to_bool(ntp) and data and ntime:
        d = data.split('-')
        t = ntime.split(':')
        config['RTC'].datetime((int(d[0]), int(d[1]), int(d[2]), int(t[0]), int(t[1]), 0, 0, 0))
    gc.collect()                                                        #Очищаем RAM
    

def update_config(mode=None, ssid=None, pssw=None, tz=None, \
                    dts=None, settm=None, pwr=None, ton=None, toff=None, wall=None, 
                    wtab= None, rw=None):
    conf = read_write_config()
    gc.collect()                                                        #Очищаем RAM
    if rw == 'w':
        conf['MODE_WiFi'] = mode if mode else conf['MODE_WiFi']         # Режим работы WiFi AP или ST
        conf['ssid'] = ssid if ssid else conf['ssid']                   # SSID для подключения к WiFi
        conf['wf_pass'] = pssw if pssw else conf['wf_pass']             # Пароль для подключения к WiFi
        conf['timezone'] = int(tz) if tz else conf['timezone']          # Временная зона
        conf['DST'] = str_to_bool(dts) if dts else conf['DST']          # Переход с летнего на зимнее время
        conf['SET_TEMP'] = settm if settm else conf['SET_TEMP']         # Температура в помещении при которой включиться отопление
        conf['DAY_POWER'] = pwr if pwr else conf['DAY_POWER']           # Уменьшение мощности в дневное время в %
        conf['TIME_ON'] = ton if ton else conf['TIME_ON']               # Время включения при работе по расписанию
        conf['TIME_OFF'] = toff if toff else conf['TIME_OFF']           # Время выключения при работе по расписанию
        conf['WORK_ALL'] = str_to_bool(wall) if wall else conf['WORK_ALL']  # Режим работы - постоянный обогрев
        conf['WORK_TAB'] = str_to_bool(wtab) if wtab else conf['WORK_TAB']  # Режим работы - по рассписанию
        read_write_config(cfg=conf)
    config['DEBUG'] = conf['DEBUG']
    config['MODE_WiFi'] = conf['MODE_WiFi']
    config['ssid'] = conf['ssid']
    config['wf_pass'] = conf['wf_pass']
    config['timezone'] = conf['timezone']
    config['DST'] = conf['DST']
    config['SET_TEMP'] = conf['SET_TEMP']
    config['DAY_POWER'] = conf['DAY_POWER']
    config['TIME_ON'] = conf['TIME_ON']
    config['TIME_OFF'] = conf['TIME_OFF']
    config['WORK_ALL'] = conf['WORK_ALL']
    config['WORK_TAB'] = conf['WORK_TAB']
    config['DS_K'] = conf['DS_K']
    gc.collect()                                                        #Очищаем RAM


def setting_update(timeon=None, timeoff=None, temph=None, workmod=None, pwr=None):
    def on_off(tstr):
        t = tstr.split(':')
        if int(t[0]) >= 0 and int(t[0]) <= 23:
            if int(t[1]) >= 0 and int(t[1]) <= 59:
                out = (0, 0, 0, int(t[0]), int(t[1]), 0, 0, 0,)
            else: out = None
        else: out = None
        return out

    def theat(temph):
        if float(temph) >= 15.00 and float(temph) <= 30.00:
            t = round(float(temph), 1)
        else: t = None
        return t
        
    def pwmpower(pwr):
        if int(pwr) >= 10.00 and int(pwr) <= 90.00:
            p = int(pwr)
        else: p = None
        return p

    on = on_off(timeon) if timeon else None
    off = on_off(timeoff) if timeoff else None
    if workmod:
        wal = 'True' if workmod == 'contin' else 'False'
        wtb = 'True' if workmod == 'schedule' else 'False'
        if workmod == 'offall':
            wal, wtb = 'False', 'False'
    else:
        wal, wtb, wot = None, None, None
    t = theat(temph) if temph else None
    p = pwmpower(pwr) if pwr else None
    update_config(settm=t, pwr=p, ton=on, toff=off, wall=wal, 
                    wtab=wtb, rw='w')


def require_auth(func):
    def auth(req, resp):
        auth = req.headers.get(b"Authorization")
        if not auth:
            yield from resp.awrite(
                'HTTP/1.0 401 NA\r\n'
                'WWW-Authenticate: Basic realm="Electric-Boiler-Control"\r\n'
                '\r\n')
            return
        auth = auth.split(None, 1)[1]
        auth = ubinascii.a2b_base64(auth).decode()
        req.username, req.passwd = auth.split(":", 1)
        if setpasswd(req.username.lower(), req.passwd) == read_write_root():
            yield from func(req, resp)
        else:
            yield from picoweb.start_response(resp)
            yield from resp.awrite(http_head)
            yield from resp.awrite('{}{}{}'.format(div_cl_header, span_err_pasw, div_end))
            yield from resp.awrite(http_footer)
    gc.collect()                                                        #Очищаем RAM
    return auth


@app.route("/")
def index(req, resp):
    t = config['RTC_TIME']
    ton = config['TIME_ON']
    toff = config['TIME_OFF']
    yield from picoweb.start_response(resp)
    yield from resp.awrite(http_head)
    yield from resp.awrite('{}{}<br>{}'\
                .format(div_cl_header, href_adm_panel, div_end))
    yield from resp.awrite(div_cl_info)
    yield from resp.awrite('<p>{:0>2d}-{:0>2d}-{:0>2d} {:0>2d}:{:0>2d}<br>'.format(t[0], t[1], t[2], t[3], t[4]))
    yield from resp.awrite('Time zone: {}<br>'.format(config['timezone']))
    yield from resp.awrite('DST: {}<br>'.format(bool_to_str(config['DST'])))
    yield from resp.awrite('Heating: {}<br>'.format(bool_to_str(config['HEAT'])))
    yield from resp.awrite('Set: {:.1f}\'C<br>'.format(config['SET_TEMP']))
    yield from resp.awrite('Room: {:.1f}\'C<br>'.format(config['TEMP']))
    yield from resp.awrite('Continuous work: {}<br>'.format(bool_to_str(config['WORK_ALL'])))
    yield from resp.awrite('Scheduled operat: {}<br>'.format(bool_to_str(config['WORK_TAB'])))
    yield from resp.awrite('On time: {:0>2d}:{:0>2d}<br>'.format(ton[3], ton[4]))
    yield from resp.awrite('Off time: {:0>2d}:{:0>2d}<br>'.format(toff[3], toff[4]))
    yield from resp.awrite('Power set: {}%<br>'.format(config['SETPOWER']))
    yield from resp.awrite('Actual power: {}%</p>'.format(round(config['POWER']/10)))
    yield from resp.awrite(div_end)
    yield from resp.awrite(http_footer)
    gc.collect()                                                        #Очищаем RAM


@app.route('/admin')
@require_auth
def admin(req, resp):
    yield from picoweb.start_response(resp)
    yield from resp.awrite(http_head)
    yield from resp.awrite('{}{}<br>{}'.format(div_cl_header, href_adm_panel, div_end))
    if req.method == "POST":
        gc.collect()                                                    #Очищаем RAM
        yield from req.read_form_data()
        form = req.form
        if 'work_mode' and 'time_off' and 'time_on' and 'temp' and 'power' in list(form.keys()):
            setting_update(form['time_on'], form['time_off'], form['temp'], form['work_mode'], form['power'])
            yield from resp.awrite('{}{}{}'.format(div_cl_info, 'Setting the operating mode update', div_end))
        elif 'ntp' and'time' and 'daylight' and 'date' and 'tzone' in list(form.keys()):
            update_config(tz=form['tzone'], dts=form['daylight'], rw='w')
            datetime_update(form['ntp'], form['date'], form['time'])
            yield from resp.awrite('{}{}{}'.format(div_cl_info, 'Setting date and time update', div_end))
        elif 'wifi'and 'ssid'and 'pasw' in list(form.keys()):
            update_config(mode=form['wifi'], ssid=form['ssid'], pssw=form['pasw'], rw='w')
            yield from resp.awrite('{}{}{}'.format(div_cl_info, 'Setting WiFi update', div_end))        
        elif 'login' and'repassw' and 'passw' in list(form.keys()):
            if form['passw'] == form['repassw'] and setroot(form['login'], form['passw']):
                yield from resp.awrite('{}{}{}'.format(div_cl_info, 'Admin password update', div_end))
            else:
                yield from resp.awrite('{}{}{}'.format(div_cl_info, 'Admin password not update', div_end))
    if req.method == "GET":
        yield from resp.awrite('{}{}<br>{}<br>{}<br>{}<br>{}'\
                    .format(div_cl_admin, mode_temp_power, date_set, wifi_form, passw_form, div_end))
    yield from resp.awrite(http_footer)
    gc.collect()                                                        # Очищаем RAM
