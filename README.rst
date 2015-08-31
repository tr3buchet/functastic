functastic - retry all the tasks you need!
------------------------------------------

functastic is used to manage tasks that you would like to retry until a success
condition is met. it can be run single threaded or in a separate thread. task
start times, success conditions, retry attempts, retry interval, and time interval
back off can be configured.

functastic provides two classes: ``TaskHeap`` and ``Task``. ``Tasks`` wrap a function
and are appended to the ``TaskHeap`` which provides a ``loop()`` function handle
running/scheduling/retrying the ``Tasks`` until the success condition is met.
``Task's`` default success condition is that the function does not raise any
Exception and returns a non ``None`` value.

usage
~~~~~
the basic task is a wrapped function that has some attributes for
determining success and when a function should be run. The configurable
traits for a task include:

- ``func``, the function to be run
- ``args``, list of args to pass to the function
- ``kwargs``, dictionary of keyword args to pass to the function
- ``attempts``, number of times to retry (set to 0 means until success)
- ``task_timeout``, the number of seconds the function may be retried
- ``delay``, the time in between each run of the function (modified by backoff)
- ``backoff``, delay multiplier, extends the delay exponentially each iteration.
  ``backoff = 1`` is standard interval, ``backoff = 2`` doubles the time in between
  each retry
- ``start_time``, the timestamp at which the function will be run the first time
  ex ``time.time() + 30`` run 30 seconds from now
- ``success condition``, function used to determine whether the task was successful
  this iteration. defaults to no exceptions raised and a non None return value

here are a few examples of what can be done with tasks

.. code:: python

    import functastic
    import time
    f = some_function
    # this is the basic task, some_function will be retried as quickly as possible
    # until it returns a non None value and doesn't raise
    task = functastic.Task(f, args['a'])

    # let's give it only 10 tries
    task = functastic.Task(f, args['a'], attempts=10)

    # and slow it down a bit (wait 1 second between each attempt)
    task = functastic.Task(f, args['a'], attempts=10, delay=1)

    # and now let's make it backoff if at first it doesn't succeed
    # this will be run at t=[0, 1, 2, 4, 8, 16, 32, 64, 128, 256] seconds
    task = functastic.Task(f, args['a'], attempts=10, delay=1, backoff=2)

    # another way to think of a task only having a certain number of attempts
    # is to give it a timeout
    # this function will be run every 1 second for 60 seconds
    task = functastic.Task(f, args['a'], task_timeout=60, delay=1)

    # want to schedule a task to start running 60 seconds from now?
    # note that the task_timeout doesn't start counting until the first run
    # so this function will start running in 60 seconds and retry every 1
    # second for 30 seconds
    task = functastic.Task(f, args['a'], start_time=time.time()+60, delay=1,
                           task_timeout=30))

    # define your own success condition for a task
    task = functastic.Task(f, args['a'], delay=1,
                           success_condition=lambda t: t.result == 'a')
    # or change it later
    task.success_condition = lambda t: t.result == 'b'
    # you could also define a more involved function instead of lambdas
    def success(task):
        if 'some key' in task.result:
            return True

    task = functastic.Task(f, args['a'], delay=1,
                           success_condition=success)

    # Tasks can be used independently of a TaskHeap
    task = functastic.Task(f, args['a'], attempts=10)
    while task.retry:
        task()
        time.sleep(2)


putting it together with the ``TaskHeap``, I'll use a simple function
that fails pretty often both with Exceptions and return values

.. code:: python

    def usually_fails(arg):
        if random.randint(1, 4) != 1:
            raise Exception('everything is ruined')
        if random.randint(1, 4) != 2:
            return None
        print '%s ran at %s' % (arg, datetime.today())
        return arg

run a task or set of tasks and wait for them to finish

.. code:: python

    import functastic
    # add tasks and then run loop(stop=True)
    tasks = functastic.TaskHeap()
    tasks.append(functastic.Task(usually_fails, args=['a'], delay=1))
    tasks.append(functastic.Task(usually_fails, args=['b'], attempts=10, delay=1))
    tasks.loop(stop=True)

run loop in another thread and add tasks willy nilly while they run

.. code:: python

    import gevent
    import functastic
    tasks = functastic.TaskHeap(sleep=gevent.sleep)
    gevent.spawn(tasks.loop)
    tasks.append(functastic.Task(usually_fails, args=['a'], delay=1))
    tasks.append(functastic.Task(usually_fails, args=['b'], attempts=10, delay=1))

    # have to sleep here to surrender execution to the loop's thread
    while True:
        gevent.sleep()

``TaskHeap`` is also iterable and ``str(tasks)`` gives a pretty good output

.. code:: python

    import functastic
    tasks = functastic.TaskHeap()
    tasks.append(functastic.Task(usually_fails, args=['a'], delay=1))
    tasks.append(functastic.Task(usually_fails, args=['b'], attempts=10, delay=1))
    print len(tasks)
    print str(tasks)
    for task in tasks:
        print task


install
~~~~~~~

``pip install functastic`` or clone the repo and ``python setup.py install`` or
``pip install -e ./``
