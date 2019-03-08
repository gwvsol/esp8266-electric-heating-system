from picoweb import WebApp, start_response
from ubinascii import a2b_base64
from gc import collect
from hcontroll import config, bool_to_str, str_to_bool, read_write_root, read_write_config, update_config
from ubinascii import hexlify
from uhashlib import sha256

app = WebApp(__name__)

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
temp_power = """<form action='admin' method='POST'>
                <fieldset>
                    <legend>Power, Temperature</legend>
                    <p><input type="number" name="temp" size="4" min="15.0" max="30.0" step="0.1" value="20.0">'C Temperature<br>
                        <input type="number" name="power" size="4" min="10" max="90" step="5" value="50">% Day power</p>
                    <p><input type="submit" value="Set Power&Temp"></p>
                </fieldset>
            </form>"""
mode_time = """<form action='admin' method='POST'>
                <fieldset>
                    <legend>Mode, Time work</legend>
                    <p><input type="radio" name="work_mode" checked value="ON">Continuous work<br>
                        <input type="radio" name="work_mode" value="TAB">On schedule<br>
                        <input type="radio" name="work_mode" value="OFF">Turn off heating</p>
                    <p>Time<br>
                        <input type="time" name="time_on" required>On<br>
                        <input type="time" name="time_off" required>Off<br></p>
                    <p><input type="submit" value="Set Mode&Time"></p>
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


def setpasswd(login, passwd):
    return str(hexlify(sha256(str(passwd+login).encode()).digest()))


def setroot(login, passw):
    passwd = setpasswd(login, passw)
    read_write_root(passwd=passw)


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
    collect()                                                           #Очищаем RAM


def setting_update(timeon=None, timeoff=None, temph=None, mod=None, pwr=None):
    def on_off(tstr):
        t = tstr.split(':')
        return (0, 0, 0, int(t[0]), int(t[1]), 0, 0, 0,)
    on = on_off(timeon) if timeon else None
    off = on_off(timeoff) if timeoff else None
    t = round(float(temph), 1) if temph else None
    p = int(pwr) if pwr else None
    m = mod if mod else None
    update_config(settm=t, pwr=p, ton=on, toff=off, work=m, rw='w')


@app.route("/")
def index(req, resp):
    t = config['RTC_TIME']
    yield from start_response(resp)
    yield from resp.awrite(http_head)
    yield from resp.awrite('{}{}<br>{}'\
                .format(div_cl_header, href_adm_panel, div_end))
    yield from resp.awrite(div_cl_info)
    yield from resp.awrite('<p>{:0>2d}-{:0>2d}-{:0>2d} {:0>2d}:{:0>2d}</p>'.format(t[0], t[1], t[2], t[3], t[4]))
    yield from resp.awrite('<p>Time zone: {}</p>'.format(config['timezone']))
    yield from resp.awrite('<p>DST: {}</p>'.format(bool_to_str(config['DST'])))
    yield from resp.awrite('<p>Set: {:.1f}\'C</p>'.format(config['SET']))
    yield from resp.awrite('<p>Room: {:.1f}\'C</p>'.format(config['TEMP']))
    yield from resp.awrite('<p>Work Mode: {}</p>'.format(config['WORK']))
    if config['WORK'] == 'TAB':
        ton, toff = config['ON'], config['OFF']
        yield from resp.awrite('<p>On: {:0>2d}:{:0>2d}</p>'.format(ton[3], ton[4]))
        yield from resp.awrite('<p>Off: {:0>2d}:{:0>2d}</p>'.format(toff[3], toff[4]))
    yield from resp.awrite('<p>Set Power : {}%</p>'.format(config['SETPOWER']))
    yield from resp.awrite('<p>Actual Power: {}%</p>'.format(round(config['POWER']/10)))
    yield from resp.awrite(div_end)
    yield from resp.awrite(http_footer)
    collect()                                                           #Очищаем RAM


@app.route('/admin')
def admin(req, resp):
    if req.method == "POST":
        if b"Authorization" in req.headers:
            yield from start_response(resp)
            yield from resp.awrite(http_head)
            yield from resp.awrite('{}{}<br>{}'.format(div_cl_header, href_adm_panel, div_end))
            collect()                                                   #Очищаем RAM
            yield from req.read_form_data()
            form = req.form
            if 'temp' and 'power' in list(form.keys()):
                setting_update(temph=form['temp'], pwr=form['power'])
            elif 'work_mode' and 'time_off' and 'time_on' in list(form.keys()):
                setting_update(timeon=form['time_on'], timeoff=form['time_off'], mod=form['work_mode'])
            elif 'ntp' and'time' and 'daylight' and 'date' and 'tzone' in list(form.keys()):
                update_config(tz=form['tzone'], dts=form['daylight'], rw='w')
                datetime_update(form['ntp'], form['date'], form['time'])
            elif 'wifi'and 'ssid'and 'pasw' in list(form.keys()):
                update_config(mode=form['wifi'], ssid=form['ssid'], pssw=form['pasw'], rw='w')
            elif 'login' and'repassw' and 'passw' in list(form.keys()):
                setroot(form['login'], form['passw'])
            yield from resp.awrite('{}{}{}'.format(div_cl_info, 'Setting OK!', div_end))
    else:
        if b"Authorization" not in req.headers:
            yield from resp.awrite('HTTP/1.0 401 NA\r\n'
                'WWW-Authenticate: Basic realm="Picoweb Realm"\r\n'
                '\r\n')
            return
        auth = req.headers[b"Authorization"].split(None, 1)[1]
        auth = a2b_base64(auth).decode()
        username, passwd = auth.split(":", 1)
        if setpasswd(username.lower(), passwd) == read_write_root():
            yield from start_response(resp)
            yield from resp.awrite(http_head)
            yield from resp.awrite('{}{}<br>{}'.format(div_cl_header, href_adm_panel, div_end))
            yield from resp.awrite(div_cl_admin)
            yield from resp.awrite('{}<br>'.format(temp_power))
            yield from resp.awrite('{}<br>'.format(mode_time))
            yield from resp.awrite('{}<br>'.format(date_set))
            yield from resp.awrite('{}<br>'.format(wifi_form))
            yield from resp.awrite('{}<br>'.format(passw_form))
            yield from resp.awrite(div_end)
        else:
            yield from start_response(resp)
            yield from resp.awrite(http_head)
            yield from resp.awrite('{}{}{}'.format(div_cl_header, span_err_pasw, div_end))
    yield from resp.awrite(http_footer)
    collect()                                                           # Очищаем RAM
