#!/usr/bin/python
__metaclass__ = type

# Create and maintain periodic disk pool snapshot tasks.

DOCUMENTATION = '''
---
module: pool_snapshot_task
short_description: Maintain periodic disk pool snapshot tasks.
description:
  - Creates, deletes, and configures disk pool snapshot tasks.
options:
  allow_empty:
    description:
      - When true, empty snapshots may be created. This can be useful when
        there are two overlapping sets of snapshots, e.g., a daily set
        and a weekly set: the weekly snapshot may be empty because the daily
        one already contains the changes to the filesystem, but you still
        want to keep the weekly snapshot when the daily one has expired.
    type: bool
  begin_time:
    description:
      - Time at which to begin taking snapshots. This is a string in
        the form "HH:MM"
      - See also C(end_time).
    type: str
  dataset:
    description:
      - The name of the dataset to snapshot. This can be a pool, ZFS
        dataset, or zvol.
    type: str
    required: true
  enabled:
    description:
      - Whether this snapshot task is enabled.
    type: str
  end_time:
    description:
      - Time at which to stop taking snapshots. This is a string in
        the form "HH:MM"
      - See also C(begin_time).
    type: str
  exclude:
    description:
      - A list of child datasets to exclude from snapshotting.
      - If a snapshot task is non-recursive, it may not have an exclude
        list, so if you specify a non-empty exclude list to a non-recursive
        task, this module will silently clear it.
    type: list
    elements: str
  lifetime_unit:
    description:
      - A unit of time for the snapshot lifetime before it is deleted.
        One of the following units of time:
        C(hour), C(day), C(week), C(month), C(year),
        optionally pluralized.
      - Along with C(lifetime_value), specifies the length of time a
        snapshot will be kept before being deleted.
    type: str
    choices: [ hour, hours, day, days, week, weeks, month, months, year, years ]
  lifetime_value:
    description:
      - The number of units of time that the snapshot will exist before
        it is deleted. Used in conjunction with C(lifetime_unit).
    type: int
  match:
    description:
      - A snapshot task does not have a name or other visible unique
        identifier, so the C(match) option provides a way of specifying
        which of several tasks the play is configuring, as well as
        telling whether the task exists yet or not.
      - The C(match) option is a dict with one or more keywords
        identifying the task. At least one must be provided.
      - If the C(state) option is C(present), only the first matching
        dataset will be updated. If C(state) is C(absent), all matching
        datasets will be deleted.
    required: true
    suboptions:
      dataset:
        description:
          - Name of the dataset being snapshotted. This can be a pool,
            dataset, or zvol.
        type: str
      name_format:
        description:
          - This is a regular expression that the C(name_format) option must
            match. The idea being that you can name your snapshots something
            like C(daily-%Y%m%d), and identify them by the prefix, using
            C(name_format: ^daily-).
        type: str
  name_format:
    description:
      - A template specifying the name of the snapshot. This must include
        the strings "%Y", "%m", "%d", "%H", and "%M". Their meanings are
        as in C(strftime): year, month, date, hour, and minute.
        Other C(strftime) sequences may also be included.
    type: str
    required: true
  recursive:
    description:
      - Whether to take snapshots of the child datasets, as well as of
        the dataset itself.
    type: bool
  state:
    description:
      - Whether the task should exist or not.
    type: str
    choices: [ absent, present ]
    default: present
  minute:
    description:
      - Minute when the task should run, in cron format.
    type: str
  hour:
    description:
      - Hour when the task should run, in cron format.
    type: str
  day:
    description:
      - Day of month when the task should run, in cron format.
    type: str
  month:
    description:
      - Month when the task should run, in cron format.
    type: str
  weekday:
    description:
      - Day of week when the task should run, in cron format.
    type: str
'''

# XXX
EXAMPLES = '''
'''

# XXX
RETURN = '''
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.arensb.truenas.plugins.module_utils.middleware \
    import MiddleWare as MW
import re


def main():
    # Required arguments:
    # - dataset (path)
    # - recursive (bool)
    #   I don't know what a good default might be
    # - lifetime_value (int)
    # - lifetime_unit (enum)
    # - naming_schema (str)
    # - schedule (cron job)
    #
    # Other arguments:
    # - exclude (list(path))
    # - allow_empty (bool)
    # - enabled (bool)

    # dataset(str): name of the pool, volume, filesystem being backed up,
    #   e.g., "tank", "tank/iocage", "tank/iocage/download",
    #   "tank/iocage/download/13.3-RELEASE"
    module = AnsibleModule(
        argument_spec=dict(
            match=dict(type='dict', required=True,
                       options=dict(
                           # id=dict(type='int'),
                           dataset=dict(type='str'),
                           name_format=dict(type='str'),
                           # recursive=dict(type='bool'),
                           # lifetime=dict(type='str'),
                       )),
            state=dict(type='str', default='present',
                       choices=['absent', 'present']),
            dataset=dict(type='str', required=True),
            recursive=dict(type='bool', required=True),
            lifetime_value=dict(type='int', required=True),
            lifetime_unit=dict(type='str', required=True,
                               choices=['hour', 'hours', 'HOUR', 'HOURS',
                                        'day', 'days', 'DAY', 'DAYS',
                                        'week', 'weeks', 'WEEK', 'WEEKS',
                                        'month', 'months', 'MONTH', 'MONTHS',
                                        'year', 'years', 'YEAR', 'YEARS']),
            name_format=dict(type='str', required=True),
            begin_time=dict(type='str'),
            end_time=dict(type='str'),
            exclude=dict(type='list', elements='str'),
            allow_empty=dict(type='bool'),
            enabled=dict(type='bool'),

            # Time specification copied from the builtin.cron module.
            minute=dict(type='str'),
            hour=dict(type='str'),
            day=dict(type='str', aliases=['dom']),
            month=dict(type='str'),
            weekday=dict(type='str', aliases=['dow']),
            ),
        supports_check_mode=True,
    )

    result = dict(
        changed=False,
        msg=''
    )

    mw = MW()

    # Assign variables from properties, for convenience
    match = module.params['match']
    state = module.params['state']
    dataset = module.params['dataset']
    recursive = module.params['recursive']
    lifetime_unit = module.params['lifetime_unit']
    lifetime_value = module.params['lifetime_value']
    name_format = module.params['name_format']
    minute = module.params['minute']
    hour = module.params['hour']
    day = module.params['day']
    month = module.params['month']
    weekday = module.params['weekday']
    begin_time = module.params['begin_time']
    end_time = module.params['end_time']
    exclude = module.params['exclude']
    allow_empty = module.params['allow_empty']
    enabled = module.params['enabled']
    allow_empty = module.params['allow_empty']

    # Convert the 'lifetime_unit' value to what middlewared expects.
    lifetime_unit = {
        'hour': 'HOUR',
        'hours': 'HOUR',
        'HOURS': 'HOUR',
        'day': 'DAY',
        'days': 'DAY',
        'DAYS': 'DAY',
        'week': 'WEEK',
        'weeks': 'WEEK',
        'WEEKS': 'WEEK',
        'month': 'MONTH',
        'months': 'MONTH',
        'MONTHS': 'MONTH',
        'year': 'YEAR',
        'years': 'YEAR',
        'YEARS': 'YEAR',
        }[lifetime_unit]

    # Make sure that 'begin_time' and 'end_time' match ^\d?\d:\d\d$.
    if begin_time is not None:
        begin_time = begin_time.trim()
        if re.match("^\\d\\d?:\\d\\d$", begin_time) is None:
            module.fail_json(msg=f"Illegal value for begin_time: {begin_time}."
                             " Should be of the form HH:MM.")
    if end_time is not None:
        end_time = end_time.trim()
        if re.match("^\\d\\d?:\\d\\d$", end_time) is None:
            module.fail_json(msg=f"Illegal value for end_time: {end_time}."
                             " Should be of the form HH:MM.")

    # Look up the task.
    # Construct a set of criteria based on 'match'
    # "~" matches a regular expression, e.g., ["shell", "~", ".*zsh.*"]
    if match is None:
        module.fail_json(msg="No match conditions given.")

    queries = []
    if 'id' in match and match['id'] is not None:
        queries.append(["id", "=", match['id']])
    if 'dataset' in match and match['dataset'] is not None:
        queries.append(["dataset", "=", match['dataset']])
    if 'name_format' in match and match['name_format'] is not None:
        queries.append(["naming_schema", "~", match['name_format']])
    # result['queries'] = queries
    if len(queries) == 0:
        # This can happen if the module spec includes some new match
        # options, but the code above doesn't parse them correctly or
        # something.
        # Also note the slightly different error message.
        module.fail_json(msg="No match conditions found.")

    # Note that 'matching_tasks' is the list of all tasks that match
    # the 'match' option, so we can delete them all if 'state==absent'.
    # 'task_info' is the first matching task, which we'll use when
    # creating and updating a task.
    try:
        matching_tasks = mw.call("pool.snapshottask.query", queries)
        if len(matching_tasks) == 0:
            # No such task
            task_info = None
        else:
            # Task exists
            task_info = matching_tasks[0]
    except Exception as e:
        module.fail_json(msg=f"Error looking up snapshot task {name}: {e}")

    # First, check whether the task even exists.
    if task_info is None:
        # Task doesn't exist

        if state == 'present':
            # Task is supposed to exist, so create it.

            # Collect arguments to pass to pool.snapshottask.create()
            arg = {
                "dataset": dataset,
                "recursive": recursive,
                "lifetime_value": lifetime_value,
                "lifetime_unit": lifetime_unit,
                "naming_schema": name_format,
            }

            if begin_time is not None:
                arg['begin'] = begin_time

            if end_time is not None:
                arg['end'] = end_time

            if exclude is not None:
                # middlewared throws an error if exclude is nonempty,
                # but recursive isn't true.
                # recursive defaults to false.
                if recursive is not None and recursive:
                    arg['exclude'] = exclude
                # Otherwise, quietly pretend that 'exclude' wasn't specified.

            if allow_empty is not None:
                arg['allow_empty'] = allow_empty

            if enabled is not None:
                arg['enabled'] = enabled

            if minute is not None:
                arg['minute'] = minute

            if hour is not None:
                arg['hour'] = hour

            if hour is not None:
                arg['hour'] = hour

            if day is not None:
                arg['dom'] = day

            if month is not None:
                arg['month'] = month

            if weekday is not None:
                arg['dow'] = weekday

            result['changes'] = arg
            if module.check_mode:
                result['msg'] = "Would have created snapshot task. " \
                    "See 'changes'."
            else:
                #
                # Create new task
                #
                try:
                    err = mw.call("pool.snapshottask.create", arg)
                except Exception as e:
                    module.fail_json(msg=f"Error creating snapshot task: {e}")

                # Return whichever interesting bits
                # pool.snapshottask.create() returned.
                result['task_id'] = err.id

            result['changed'] = True
        else:
            # Task is not supposed to exist.
            # All is well
            result['changed'] = False

    else:
        # Task exists
        if state == 'present':
            # Task is supposed to exist

            # Make list of differences between what is and what should
            # be.
            arg = {}

            if dataset is not None and task_info['dataset'] != dataset:
                arg['dataset'] = dataset

            if recursive is not None and task_info['recursive'] != recursive:
                arg['recursive'] = recursive

            if lifetime_value is not None and \
               task_info['lifetime_value'] != lifetime_value:
                arg['lifetime_value'] = lifetime_value

            if lifetime_unit is not None and \
               task_info['lifetime_unit'] != lifetime_unit:
                arg['lifetime_unit'] = lifetime_unit

            if name_format is not None and \
               task_info['naming_schema'] != name_format:
                arg['naming_schema'] = name_format

            if minute is not None and task_info['minute'] != minute:
                arg['minute'] = minute

            if hour is not None and task_info['hour'] != hour:
                arg['hour'] = hour

            if day is not None and task_info['day'] != day:
                arg['day'] = day

            if month is not None and task_info['month'] != month:
                arg['month'] = month

            if weekday is not None and task_info['weekday'] != weekday:
                arg['weekday'] = weekday

            if begin_time is not None and \
               task_info['begin_time'] != begin_time:
                arg['begin_time'] = begin_time

            if end_time is not None and task_info['end_time'] != end_time:
                arg['end_time'] = end_time

            if allow_empty is not None and \
               task_info['allow_empty'] != allow_empty:
                arg['allow_empty'] = allow_empty

            # For exclude, perform a set comparison because order
            # doesn't matter.
            if exclude is not None and \
               set(task_info['exclude']) != set(exclude):
                arg['exclude'] = exclude

            # If the task is non-recursive, the exclusion list must
            # be empty.
            # Why would the task wind up non-recursive? Either:
            # a) it was already non-recursive, and we're not changing it.
            # b) we're explicitly setting it to non-recursive.
            if ((recursive is False) or \
                (task_info['recursive'] is False)):
                # If the exclusion list was already empty, and
                # module.params doesn't change that, this assignment
                # is unnecessary. But I don't think this can lead to
                # an unnecessary midclt call, so I don't care a lot.
                arg['exclude'] = []

            if allow_empty is not None and \
               task_info['allow_empty'] != allow_empty:
                arg['allow_empty'] = allow_empty

            if enabled is not None and task_info['enabled'] != enabled:
                arg['enabled'] = enabled

            # If there are any changes, pool.snapshottask.update()
            if len(arg) == 0:
                # No changes
                result['changed'] = False
            else:
                #
                # Update task.
                #
                result['changes'] = arg
                if module.check_mode:
                    result['msg'] = "Would have updated snapshot task. " \
                        "See 'changes'."
                else:
                    try:
                        err = mw.call("pool.snapshottask.update",
                                      task_info['id'],
                                      arg)
                    except Exception as e:
                        module.fail_json(msg=("Error updating snapshot task "
                                              f"with {arg}: {e}"))
                        # Return any interesting bits from err
                        result['status'] = err['status']
                        result['update_status'] = err
                result['changed'] = True
        else:
            # Task is not supposed to exist

            # Delete all matching tasks.
            if module.check_mode:
                result['msg'] = "Would have deleted snapshot tasks."
                result['deleted_tasks'] = matching_tasks
            else:
                try:
                    #
                    # Delete tasks.
                    #

                    # Return a list of all deleted tasks.
                    result['deleted_tasks'] = []

                    for task in matching_tasks:
                        err = mw.call("pool.snapshottask.delete",
                                      task['id'])
                        result['deleted_tasks'].append(task)
                except Exception as e:
                    module.fail_json(msg=f"Error deleting snapshot task: {e}")
            result['changed'] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
