#!/usr/bin/python
__metaclass__ = type

# Create and manage users.

DOCUMENTATION='''
module: user
short_description: Manage user accounts
description:
  - Add, change, and delete user accounts.
options:
  name:
    description:
      - Name of the user to manage.
    type: str
    required: true
    aliases: [ user ]
  uid:
    description:
      - Set the I(UID) of the user.
    type: int
  comment:
    description:
      - The full name (I(GECOS) field) of the user.
    type: str
    default: ""
  group:
    description:
      - The name of the user's primary group.
      - Required unless C(create_group) is true.
    type: str
  groups:
    description:
      - List of additional groups user will be added to.
      - If C(append) is true, the user will be added to all of the groups
        listed here.
      - If C(append) is false, then in addition, the user will be removed
        from all other groups (except the primary).
    type: list
  append:
    description:
      - If true, the user will be added to the groups listed in C(groups),
        but not removed from any other groups.
      - If false, the user will be added to the groups listed in C(groups),
        and removed from any other groups.
    type: bool
    default: false
  create_group:
    description:
      - If true, create a new group with the same name as the user.
      - If such a group already exists, it is used and no new group is
        created.
    type: bool
    default: false
  password:
    description:
      - User's password, as a crypted string.
      - Required unless C(password_disabled) is true.
      - Note: Currently there is no way to check whether the password
        needs to be changed.
    type: str
  password_disabled:
    description:
      - If true, the user's password is disabled.
      - They can still log in through other methods (e.g., ssh key).
      - This is not a flag: if you set C(password_disabled=true) on a user,
        the password field in C(/etc/master.passwd) is set to C(*), so
        if you set C(password_disabled=false) again, they won't be able to
        log in with their old password.
      - If you need that functionality, do something like prepend "*LOCK*"
        to the crypt string when locking a user, then remove it when
        unlocking.
    type: bool
    default: false
  state:
    description:
      - Whether the user should exist or not.
    type: str
    choices: [ absent, present ]
    default: present
  delete_group:
    description:
      - If true, delete the user's primary group if it is not being used
        by any other users.
      - If false, the primary group stays, even if it is now empty.
      - Only used when deleting a user.
    type: bool
    default: true
'''

EXAMPLES = '''
XXX
- name: Create an ordinary user and their group
  ooblick.truenas.user:
    name: bob
    comment: "Bob the User"
    create_group: yes
    password: "<encrypted password string>"

- name: Create an ordinary user and put them into an existing group
  ooblick.truenas.user:
    name: bob
    comment: "Bob the User"
    group: users
    password: "<encrypted string>"

- name: Create a user without a working password
  ooblick.truenas.user:
    name: bob
    comment: "Bob the User"
    group: bobsgroup
    password_disabled: yes

- name: Delete a user
  ooblick.truenas.user:
    name: bob
    state: absent

- name: Delete a user, but keep their primary group, even if it's now empty.
  ooblick.truenas.user:
    name: bob
    state: absent
    delete_group: no
'''

# XXX - XXX - Return the UID of new user.
RETURN = '''
'''

from ansible.module_utils.basic import AnsibleModule, missing_required_lib
from ansible_collections.ooblick.truenas.plugins.module_utils.middleware \
    import MiddleWare as MW

def main():
    # user.create() arguments:
    # - uid (int)
    # - username (str)
    # - group(int) - Required if create_group is false.
    # - create_group(bool)
    # - home(str)
    # - home_mode(str)
    # - shell(str) - Choose from user.shell_choices() (reads /etc/shells)
    # - full_name(str)
    # - email(str|null?)
    # - password(str) - Required if password_disabled is false
    # - password_disabled(bool)
    # - locked(bool)
    # - microsoft_account(bool)
    # - smb(bool) - Does user have access to SMB shares?
    # - sudo(bool)
    # - sudo_nopasswd(bool)
    # - sudo_commands(bool)
    # - sshpubkey(str|null?)
    # - groups(list)
    # - attributes(obj) - Arbitrary user information
    module = AnsibleModule(
        argument_spec=dict(
            # TrueNAS user.create arguments:
            uid=dict(type='int'),
            name=dict(type='str', required=True, aliases=['user']),

            # XXX - I'm not sure what the sensible default here is.
            create_group=dict(type='bool', default=False),

            password=dict(type='str', default='', no_log=True),

            # We set no_log explicitly to False, because otherwise
            # module_utils.basic sees "password" in the name and gets
            # worried.
            password_disabled=dict(type='bool', default=False, no_log=False),


            # From builtin.user module
            # - name(str)
            # - uid(int)
            # - comment(str) - GECOS
            comment=dict(type='str', default=''),
            # - hidden(bool)
            # - non_unique(bool)
            # - seuser(str) - SELinux user type
            # - group(str) - primary group name
            group=dict(type='str'),
            # - groups(list) - List of group names
            # - append(bool) - whether to add to or set group list
            # - shell(str)
            # - home(path)
            # - skeleton(path) - skeleton directory
            # - password(str) - crypted password
            # - state(absent, present)
            state=dict(type='str', default='present',
                       choices=['absent', 'present']),

            delete_group=dict(type='bool', default=True)
            # - create_home(bool)
            # - move_home(bool)
            # - system(bool) - system account, whatever that means
            # - force(bool) - Force removing user and dirs
            # - remove(bool) - When removing user, remove directories as well.
            # - login_class(str)
            # - generate_ssh_key(bool)
            # - ssh_key_bits(int)
            # - ssh_key_type(str) - default "rsa"
            # - ssh_key_file(path) - relative to home directory
            # - ssh_key_comment(str)
            # - ssh_key_passphrase(str)
            # - update_password(always, on_create)
            # - expires(float) - expiry time in epoch
            # - password_lock(bool) - Prevent logging in with password
            # - local(bool) - Local account, not AD or NIS.
            # - profile(str) - Solaris
            # - authorization(str) - Solaris
            # - role(str) - Solaris
        ),
        supports_check_mode=True,
        required_if=[
            ['password_disabled', False, ['password']]
        ]
    )

    result = dict(
        changed=False,
        msg=''
    )

    module.debug("Inside ooblick.truenas.user")

    mw = MW()

    # Assign variables from properties, for convenience
    uid = module.params['uid']
    username = module.params['name']
    password = module.params['password']
    password_disabled = module.params['password_disabled']
    group = module.params['group']
    create_group = module.params['create_group']
    comment = module.params['comment']
    state = module.params['state']
    delete_group = module.params['delete_group']

    # Look up the user.
    # Note that
    #   user.query [["username","=","ansible"]]
    # returns a lot more detail than
    #   user.get_user_obj {"username":"ansible"}
    # I suspect that get_user_obj() just looks up an entry in
    # /etc/passwd, while query() has a more generalized notion of what
    # a user is.
    try:
        user_info = mw.call("user.query",
                            [["username", "=", username]])
        # user.query() returns an array of results, but the query
        # above can only return 0 or 1 results.
        if len(user_info) == 0:
            # No such user
            user_info = None
        else:
            # User exists
            user_info = user_info[0]
    except Exception as e:
        module.fail_json(msg=f"Error looking up user {username}: {e}")

    # XXX - Mostly for debugging:
    result['user_info'] = user_info

    # First, check whether the user even exists.
    if user_info is None:
        # User doesn't exist

        if state == 'present':
            # User is supposed to exist, so create it.

            # Collect arguments to pass to user.create()
            arg = {
                "username": username,

                # full_name is required.
                "full_name": comment,

                # Either password_disabled == True, or password must be
                # supplied.
                "password": password,
                "password_disabled": password_disabled,
            }

            if uid is not None:
                arg['uid'] = uid

            # Look up the primary group. user.create() requires
            # a group number (not a GID!), but for compatibility with
            # the Ansible builtin.user module, we want to be able to
            # use a string for "group". So we need to look the group
            # up by name.
            if create_group:
                arg['group_create'] = True
            else:
                try:
                    group_info = mw.call("group.query",
                                         [["group", "=", group]])
                except Exception as e:
                    module.fail_json(msg=f"Error looking up group {group}: {e}")

                if len(group_info) == 0:
                    # No such group.
                    # If we got here, presumably it's because a primary
                    # group was set through 'group', but 'create_group'
                    # was not set. 
                    group_info = None
                else:
                    group_info = group_info[0]

                arg['group'] = group_info['id']

                # XXX - Just for debugging.
                result['group_info'] = group_info

            if module.check_mode:
                result['msg'] = f"Would have created user {username}"
            else:
                #
                # Create new user
                #
                try:
                    err = mw.call("user.create", arg)
                    result['msg'] = err
                except Exception as e:
                    module.fail_json(msg=f"Error creating user {username}: {e}")

        else:
            # User is not supposed to exist.
            # All is well
            result['changed'] = False
    else:
        # User exists
        if state == 'present':
            # User is supposed to exist

            # XXX - Make list of differences between what is and what
            # should be.

            # user.query() output:
            # [
            #   {
            #     "id": 37,
            #     "uid": 1001,
            #     "username": "arnie",
            #     "unixhash": "*",
            #     "smbhash": "*",
            #     "home": "/nonexistent",
            #     "shell": "/bin/csh",
            #     "full_name": "",
            #     "builtin": false,
            #     "smb": true,
            #     "password_disabled": true,
            #     "locked": false,
            #     "sudo": false,
            #     "sudo_nopasswd": false,
            #     "sudo_commands": [],
            #     "microsoft_account": false,
            #     "attributes": {},
            #     "email": null,
            #     "group": {
            #       "id": 47,
            #       "bsdgrp_gid": 1001,
            #       "bsdgrp_group": "arnie",
            #       "bsdgrp_builtin": false,
            #       "bsdgrp_sudo": false,
            #       "bsdgrp_sudo_nopasswd": false,
            #       "bsdgrp_sudo_commands": [],
            #       "bsdgrp_smb": false
            #     },
            #     "groups": [
            #       43
            #     ],
            #     "sshpubkey": null,
            #     "local": true,
            #     "id_type_both": false
            #   }
            # ]

            arg = {}

            # elements in argument_spec:
            # - name (username)
            # - password (crypt)
            # - password_disabled
            # - comment
            # - group (primary group)

            if uid is not None:
                arg['uid'] = uid

            # XXX - There's probably a way to get user.query() to
            # return the current crypt string of a user,but I don't
            # know what that is. Until then, we can't check whether
            # the password needs to be changed.

            # if password is not None and user_info['password'] != password:
            #     arg['password'] = password

            if user_info['password_disabled'] != password_disabled:
                arg['password_disabled'] = password_disabled

            if comment is not None and user_info['full_name'] != comment:
                arg['full_name'] = comment

            # Check primary group.
            if group is not None and user_info['group']['bsdgrp_group'] != group:
                # XXX - Look up group?
                try:
                    grp = mw.call("group.query",
                                  [["group", "=", group]])
                except Exception as e:
                    module.fail_json(msg=f"Error looking up group {group}: {e}")

                # As above, 'grp' is an array of 0 or 1 elements.
                if len(grp) == 0:
                    # The lookup was successful, and successfully
                    # found that there's no such group.
                    module.fail_json(msg=f"No such group: {group}")
                arg['group'] = grp[0]['id']

            # XXX - Add 'groups', 'append'
            # user_info['groups'] is a list of ints. Each one is a group
            # to look up.
            # I think the easy way to do this is:
            # group.query [["id", "in", [1, 2, 20, 605]]]
            #
            # if append is true:
            #   check the groups in 'groups', and make sure
            #   user is in all of them.
            # else:
            #   Same, but make sure user is not in any other groups.

            # XXX - If there are any, user.update()
            if len(arg) == 0:
                # No changes
                result['changed'] = False
            else:
                #
                # Update user.
                #
                if module.check_mode:
                    result['msg'] = f"Would have updated user {username}: {arg}"
                else:
                    try:
                        err = mw.call("user.update",
                                      user_info['id'],
                                      arg)
                    except Exception as e:
                        module.fail_json(msg=f"Error updating user {usename} with {arg}: {e}")
                result['changed'] = True

        else:
            # User is not supposed to exist

            if module.check_mode:
                result['msg'] = f"Would have deleted user {username}"
            else:
                try:
                    #
                    # Delete user.
                    #
                    err = mw.call("user.delete",
                                  user_info['id'],
                                  {"delete_group": delete_group})
                except Exception as e:
                    module.fail_json(msg=f"Error deleting user {username}: {e}")
            result['changed'] = True

    module.exit_json(**result)

### Main
if __name__ == "__main__":
    main()
