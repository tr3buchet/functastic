#!/usr/bin/env python
#
# Copyright 2015 Trey Morris
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
import time
import heapq
from datetime import datetime

import logging
try:  # Python 2.7+
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

LOG = logging.getLogger(__name__)
LOG.addHandler(NullHandler())


class TaskHeap(object):
    def __init__(self, sleep=time.sleep, interval=0.1):
        """
        sleep: the sleep function loop() uses: ex gevent.sleep
               can also monkey patch time.sleep and not bother passing it in

        interval: the interval at which loop() checks for any ready tasks.
                  loop() will run any ready tasks each iteration and then sleep
                  for interval before seeing if more tasks ar ready

        """
        self.tasks = []
        self.sleep = sleep
        self.interval = interval

    def loop(self, stop=False):
        """
        stop: if stop is True, loop() will return when there are no more tasks
              if stop is False, loop() runs forever waiting for new tasks
        """
        while not stop or (stop and self.tasks):
            if self.tasks and time.time() >= self.tasks[0].next_run_at:
                task = heapq.heappop(self.tasks)
                task()
                if task.retry:
                    self.append(task)
            else:
                self.sleep(self.interval)

    def __str__(self):
        s = '%s<sleep=%s, interval=%s, tasks=%s>'
        return s % (self.sleep, self.interval, [str(t) for t in self.tasks])

    def __iter__(self):
        return iter(self.tasks)

    def __len__(self):
        return len(self.tasks)

    def append(self, task):
        heapq.heappush(self.tasks, task)


class Task(object):
    def __init__(self, func, args=None, kwargs=None, attempts=0,
                 task_timeout=None, delay=0, backoff=1,
                 start_time=None, success_condition=None):
        """
        func: the function this task will run
        args: args to func
        kwargs: kwargs to func

        attempts: number of times func will be run waiting for success.
                  defaults to 0 which means it will run until the success
                  condition is met
        task_timeout: duration the task has to reach success condition
                      will LOG.error and stop retrying
        delay: the delay in seconds between each run of this task
        backoff: delay multiplier, extends the delay exponentially each
                 iteration. delay 1 backoff 2 is 1 2 4 8 16 32..
        start_time: the timestamp at which func will run the first time
                    defaults to now. ex `time.time() + 10` is 10s from now
        success_condition: function used to determine whether a task run was
                           successful. detaults to no exceptions raised and
                           any non None return value.
                           ex `lambda task: task.result == 'success'`
        """
        self._start_time = start_time or time.time()
        self._attempts_left = attempts
        self._task_timeout = self._start_time + (task_timeout or 315400000)
        self._delay = delay
        self._backoff = backoff

        self._func = func
        self._args = args or []
        self._kwargs = kwargs or {}

        self.result = None
        self.exception = None
        self.success_condition = (success_condition or
                                  self.default_success_condition)
        self.next_run_at = self._start_time
        self.retry = False

    def __str__(self):
        s = ('%s<func=%s (%s, %s), attempts_left=%s, '
             'next_run_at=%s, task_timeout=%s, last_result=%s, '
             'last_exception=%s>')
        return s % (self.__class__.__name__, self._func.__name__,
                    self._args, self._kwargs, self._attempts_left,
                    datetime.fromtimestamp(self.next_run_at),
                    datetime.fromtimestamp(self._task_timeout),
                    self.result, self.exception)

    def __lt__(self, bro):
        return self.next_run_at < bro.next_run_at

    def __call__(self):
        LOG.info('attempting task: %s' % self)
        self.result = None
        self.exception = None
        try:
            self.result = self._func(*self._args, **self._kwargs)
        except Exception as e:
            self.exception = e
            LOG.exception(e)

        self.retry = False
        if not self.success_condition(self):
            self.retry = True
            self._attempts_left = self._attempts_left - 1
            self.next_run_at = self.next_run_at + self._delay
            self._delay = self._delay * self._backoff
            LOG.warn('task attempt failed: %s' % self)
            if self._attempts_left == 0:
                LOG.error('task attempts exhausted: %s' % self)
                self.retry = False
            elif self.next_run_at > self._task_timeout:
                LOG.error('task timed out: %s' % self)
                self.retry = False

    @staticmethod
    def default_success_condition(task):
        return (task.result is not None and task.exception is None)
