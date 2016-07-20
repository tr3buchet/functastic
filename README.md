# functastic - retry all the tasks you need
functastic is used to manage tasks that you would like to retry until a success condition is met, or potentially forever. it can be run single threaded or in a separate thread. task start times, success conditions, retry attempts, retry interval, and time interval back off can be configured. it's important to note that all tasks are run in a single thread one after the other, so if you have a longer running task it may delay the actual start time of the task or tasks behind it in line. with this in mind, functastic works better with quick tasks for now. I'd like to have it spawn tasks as side threads in the future, but I didn't want to require the usage of any particular threading library at present.

functastic provides two classes: `TaskHeap` and `Task`. `Tasks` wrap a function and are appended to the `TaskHeap` which provides a `run()` function handle running/scheduling/retrying the `Tasks` until the success condition is met. `Task's` default success condition is that the function does not raise any Exception and returns any non `None` value.

calling a `Task` object can never raise an exception. calling a task either manually or using a `TaskHeap` will only log exceptions and potentially use them to determine success, but they won't be raised. the one exception to this rule is if your custom `success_condition` function raises an exception, so be careful writing them. `Task` will also raise on initialization if you provide a `success_condition` that isn't callable.


## install
`pip install functastic` or clone the repo and `python setup.py install` or `pip install -e` if you want to play with the code


## `Task` usage
the basic task is a wrapped function that has some attributes for determining success and when a function should be run. note that anything to do with scheduled times, delays, or timeouts are "best try". long running tasks can get in the way of the task schedule. the configurable traits for a task include:

-   `func`, the function to be run
-   `args`, list of args to pass to the function
-   `kwargs`, dictionary of keyword args to pass to the function
-   `attempts`, number of times to retry (set to 0 means until success)
-   `task_timeout`, the number of seconds the function may be retried
-   `delay`, the time in between each run of the function (modified by backoff)
-   `backoff`, delay multiplier, extends the delay exponentially each iteration. `backoff = 1` is standard interval, `backoff = 2` doubles the time in between each retry
-   `start_time`, the timestamp at which the function will be run the first time ex `time.time() + 30` run 30 seconds from now
-   `success_condition`, function used to determine whether the task was successful this iteration. defaults to no exceptions raised and a non None return value. an exception will be raised during `Task` init if `success_condition` isn't callable

here are a few examples of creating tasks.

```python
from functastic import Task
import time
f = some_function
# this is the basic task, it will have retry set to True
# until it returns a non None value and doesn't raise
task = Task(f, args['a'])

# let's give it only 10 tries. after 10 tries, retry will be set to False
task = Task(f, args['a'], attempts=10)

# and slow it down a bit (wait 1 second between each attempt).
# the delay schedules the task again 1 second after the previous
# attempt. without delay, schedule for task's next run will be immediately
# TaskHeap manages the schedules if you want to use it
task = Task(f, args['a'], attempts=10, delay=1)

# and now let's make it backoff if at first it doesn't succeed
# this will be run at t=[0, 1, 2, 4, 8, 16, 32, 64, 128, 256] seconds
task = Task(f, args['a'], attempts=10, delay=1, backoff=2)

# another way to think of a task only having a certain number of attempts
# is to give it a timeout
# this function will be run approximately every 1 second for 60 seconds
# CAUTION! long running tasks may delay things, tasks with task_timeout
#          can only be guaranteed to run once
task = Task(f, args['a'], task_timeout=60, delay=1)

# want to schedule a task to start running 60 seconds from now?
# note that the task_timeout doesn't start counting until the first run
# so this function will start running in 60 seconds and retry every 1
# second for 30 seconds
task = Task(f, args['a'], start_time=time.time()+60, delay=1,
            task_timeout=30))

# define your own success condition for a task
task = Task(f, args['a'], delay=1,
            success_condition=lambda t: t.result == 'a')
# or change it later
task.success_condition = lambda t: t.result == 'b'
# you could also define a more involved function instead of lambdas
def success(task):
    if 'some key' in task.result:
        return True

task = Task(f, args['a'], delay=1, success_condition=success)
```

#### tasks which never succeed (on purpose)

```python
from functastic import Task
# if you want a task to run over and over forever, say 10 seconds after
# it last finished, set the success condition to `lambda t: None`
# and do not specify attempts
task = Task(f, args=['a'], delay=10,
            success_condition=lambda t: None)

# this task will be run 5 times, 10 seconds after the previous run,
# regardless of what f returns or raises
task = Task(f, args=['a'], delay=10, attempts=5,
            success_condition=lambda t: None)
```

#### tasks which "succeed" by failing in some way
sometimes it makes sense to think of `success_condition` as a `break` condition.
let's say there is a function that makes requests to a webservice. it makes sense to retry if you get a `404` because you are polling for a resource to become available, but if you get another error, like `401 unauthorized`, retrying wouldn't make sense, so we want to `break` (or "succeed") if we get a non `404` exception:

```python
import requests
from functastic import Task

def handle_resource(res):
    pass

def get_thing(url):
    r = requests.get(url)
    r.raise_for_status()
    handle_resource(r.json())

# every 5 seconds attempt to fetch the resource and handle it,
# quit when there is no exception (actual success) or there is
# a non 404 exception (call failed in a bad way, so don't try it again)
task = Task(get_thing, args['http://whatever.com/resource/id'], delay=5,
            success_condition=lambda t: (t.exception and '404' not in t.exception.message or
                                         not t.exception))
```

#### using tasks without `TaskHeap`

```python
from functastic import Task

task = Task(f, args['a'], attempts=10)

# task.retry always starts as True
while task.retry:
    # calling the task calls the function
    task()
    # at this point, task.retry may have become False depending on the task
    # optionally sleep in between calls
    time.sleep(2)
```


## `TaskHeap` usage
putting `Task` together with the `TaskHeap`, I'll use a simple function that fails pretty often both with Exceptions and return values

```python
def usually_fails(arg):
    if random.randint(1, 4) != 1:
        raise Exception('everything is ruined')
    if random.randint(1, 4) != 2:
        return None
    print '%s ran at %s' % (arg, datetime.today())
    return arg
```

`TaskHeap` is iterable and works as a `bool` and `str(tasks)` gives a pretty good output

```python
from functastic import Task
from functastic import TaskHeap
tasks = TaskHeap()
tasks.append(Task(usually_fails, args=['a'], delay=1))
tasks.append(Task(usually_fails, args=['b'], attempts=10, delay=1))
if tasks:
    print len(tasks)
    print str(tasks)
    for task in tasks:
        print task
```


#### unthreaded use
run a task or set of tasks and return when they finish. without `stop=True` the
`tasks.run()` call will block forever because it won't stop iterating every
`TaskHeap` `interval`.

```python
from functastic import Task
from functastic import TaskHeap
# add tasks and then run run(stop=True)
tasks = TaskHeap()
tasks.append(Task(usually_fails, args=['a'], delay=1))
tasks.append(Task(usually_fails, args=['b'], attempts=10, delay=1))
tasks.run(stop=True)
```


#### use with threading library
`TaskHeap` works well with threading libraries. this will run the task
loop in another thread and add tasks willy nilly while they run

```python
import eventlet
from functastic import Task
from functastic import TaskHeap
# note the use of eventlet.sleep here to specify which sleep
# function TaskHeap should use, or use monkey patching
# interval can also be passed if you don't like the default 0.1s
# this sets the interval task run interval to 3 seconds
tasks = TaskHeap(sleep=eventlet.sleep, interval=3)
eventlet.spawn(tasks.run)
tasks.append(Task(usually_fails, args=['a'], delay=1))
tasks.append(Task(usually_fails, args=['b'], attempts=10, delay=1))

# have to sleep here to surrender execution to the green thread
while tasks:
    tasks.sleep()
```


#### stopping tasks
once a `TaskHeap` has been started with `run()`, it will run indefinitely
unless `stop=True` is passed in `run(stop=True)`. it can be stopped in
two different ways:
-   `stop_after()`, causes the task loop to exit once all tasks are completed
-   `stop_now()`, causes the task loop to stop as soon as possible. since the task loop is single threaded, it will only exit after finishing the current iteration. this means the current task, if there is one, will continue as planned, but all future tasks will not be run unless `run()` is called again.

```python
import eventlet
from functastic import Task
from functastic import TaskHeap

tasks = TaskHeap(sleep=eventlet.sleep)
gt = eventlet.spawn(tasks.run)
tasks.append(Task(usually_fails, args=['a'], delay=1))
tasks.append(Task(usually_fails, args=['b'], attempts=10, delay=1))

# stop the tasks thread after 5 second, gt.wait() will return almost
# instantly
tasks.sleep(5)
tasks.stop_now()
gt.wait()             # <-- this line should return quickly

# start the tasks again
gt = eventlet.spawn(tasks.run)

# this time tell the tasks loop to exit once finished
tasks.sleep()
tasks.stop_after()
gt.wait()             # <-- this line should return when all tasks complete
```
