try:
    import utime as time
except:
    import time


def _clamp(value, limits):
    lower, upper = limits
    if value is None:
        return None
    elif upper is not None and value > upper:
        return upper
    elif lower is not None and value < lower:
        return lower
    return value
    

# получение постоянно изменяющегося времени
_current_time = time.ticks_ms


class PID(object):
    """
    ПИД-регулятор
    """
    def __init__(self,
                 Kp=1.0, Ki=0.0, Kd=0.0,
                 setpoint=0,
                 sample_time=0.01,
                 output_limits=(None, None),
                 auto_mode=True,
                 proportional_on_measurement=False):
        
        #Коэфициенты пропорциональный, интегральный, диференциаотный
        self.Kp, self.Ki, self.Kd = Kp, Ki, Kd
        #Значение температуры в настоящий момент
        self.setpoint = setpoint
        #Время в секундах, которое контроллер ожидает перед расчетом нового значения. 
        #ПИД работает лучше всего, когда он постоянно вызывается (например, во время цикла), 
        #но с установленным временем выборки, так что разница во времени между каждым обновлением 
        #(близким к) постоянна. Если установлено значение None, ПИД будет вычислять новое 
        #значение каждый раз, когда он вызывается.
        self.sample_time = sample_time
        #Пределы выходных данных, заданные как итерируемые 2 элемента, например: (нижний, верхний). 
        #Выходные данные никогда не будет опускаться ниже нижнего предела или выше верхнего предела. 
        #Любой из пределов также может быть установлен на None, чтобы не иметь ограничений. 
        #Установка пределов также позволяет избежать интегрального завершения, 
        #поскольку интегральный коэффициент никогда не будет разрешен для увеличения за пределами ограничений.
        self._min_output, self._max_output = output_limits
        #Режим работы ПИД контроллера, auto mode=True или manual mode=False
        self._auto_mode = auto_mode
        #Следует ли рассчитывать пропорциональный коеффициент на входе напрямую, а не на ошибку 
        #(что является традиционным способом). Использование пропорционального измерения позволяет 
        #избежать перерегулирования для некоторых типов систем.
        self.proportional_on_measurement = proportional_on_measurement

        self._error_sum = 0
        # Вычисление времени в секундах
        self._last_time = _current_time()/1000 
        self._last_output = None
        self._proportional = 0
        self._last_input = None

    def __call__(self, input_):
        """
        Вызов ПИД-регулятора с помощью * input__* При этом происходит вычисление ошибки и возврат вычисленного 
        значения, если с момента последнего вычисления прошло sample_time. Если новое значение не вычисляется, 
        возвращается предыдущий результат (или None, если значение еще не посчитано).
        """
        #print('PID input:', input_)
        
        if not self.auto_mode: #Проверка режима ПИД регулятора
            return self._last_output
        #print('auto_mode =', self.auto_mode)

        now = _current_time()/1000 # Вычисление времени в секундах с последнего вычисления
        #print('Now:', now)
        dt = now - self._last_time
        #print('Delta Time:', dt)
        #Сревнение времени прошедшего с последнего вычисления с заданым значением
        if self.sample_time is not None and dt < self.sample_time and self._last_output is not None:
            #Если времени прошло меньше чем заданное значение, возращяем предыдущий результат
            return self._last_output

        #Вычисление ошибки
        error = self.setpoint - input_
        
        #Вычисление интегральной составляющей и суммирование с результатом
        self._error_sum += self.Ki * error * dt

        # вычисление пропорциональной составляющей
        d_input = input_ - (self._last_input if self._last_input is not None else input_)
        if not self.proportional_on_measurement:
            # пропорциональная составляющая, простое вычисление по установленному коэффициенту
            self._proportional = self.Kp * error
        else:
            # пропорциональная составляющая, вычисление и суммирование с результатом
            self._error_sum -= self.Kp * d_input
            self._proportional = 0

        # сранение сумммы пропорциональной и интегральной составляющей с установленным нижним и верхним пределом
        self._error_sum = _clamp(self._error_sum, self.output_limits)

        # compute final output
        # вычисление итогового результата(суммирование с дифференциальной составыляющей)
        output = self._proportional + self._error_sum - self.Kd * d_input
        #print('Error_sum:', output)
        
        # сранение итогового результата с установленным нижним и верхним пределом
        output = _clamp(output, self.output_limits)

        # keep track of state
        # сохрание результатов вычислений
        self._last_output = output
        # сохранение предыдущего входного значения
        self._last_input = input_
        # сохрание времени предыдущего вычисления
        self._last_time = now
        # Возращение вычисленного результата погрешности ПИД регулятора
        #print('Last out:', self._last_output)
        #print('Last input:', self._last_input)
        #print('Last time', self._last_time)
        #print('PID out:', output)
        return output

    @property
    def tunings(self):
        """Преобразование используемых контроллером данных в кортедж: (Kp, Ki, Kd)"""
        return self.Kp, self.Ki, self.Kd

    @tunings.setter
    def tunings(self, tunings):
        """Сеттер для настроек ПИД-регулятора"""
        self.Kp, self.Ki, self.Kd = tunings

    @property
    def auto_mode(self):
        """Включен или выключен контроллер в автоматическом режиме"""
        return self._auto_mode

    @auto_mode.setter
    def auto_mode(self, enabled):
        """Включение или выключение ПИД регулятора"""
        # Если enable = True, включаем, = False выключаем работу ПИД регулятора
        if enabled and not self._auto_mode:
            # переход из ручного режима в автоматический, сброс
            self._last_output = None
            self._last_input = None
            self._error_sum = 0
            self._error_sum = _clamp(self._error_sum, self.output_limits)

        self._auto_mode = enabled

    @property
    def output_limits(self):
        """
        Текущее значение выходных ограничений в виде кортеджа 
        (нижнее и верхнее значение), так же смотри значение 
        :meth:`PID.__init__`.
        """
        return (self._min_output, self._max_output)

    @output_limits.setter
    def output_limits(self, limits):
        """Сеттер установки выходных ограничений"""
        if limits is None:
            self._min_output, self._max_output = None, None
            return

        min_output, max_output = limits
        
        # проверяем нижний предел должен быть меньше верхнего предела
        if None not in limits and max_output < min_output:
            raise ValueError('lower limit must be less than upper limit')

        self._min_output = min_output
        self._max_output = max_output
        
        # сранение суммы пропорциональной и интегральной составляющей 
        # с установленным нижним и верхним пределом
        self._error_sum = _clamp(self._error_sum, self.output_limits)
        # сохранение предыдущего входного значения
        self._last_output = _clamp(self._last_output, self.output_limits)
        
