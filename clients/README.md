# Client profiles

One file per client, created the first time you run the **weekly-status-report** skill for that
client. Each file stores that client's email domain, point of contact, internal CC team, and the
Power BI project its hours come from, so later runs need only the client name.

This folder ships **empty** on purpose. It is the skill's settings store, not shared data: your
profiles stay in your own copy, and a teammate who installs this skill starts with a blank folder
and runs their own setup.

There is **one** weekly scheduled run that covers every client with a profile in this folder.
Adding a client means adding a profile here, not adding another scheduled task.

You don't need to edit these by hand. To change a client's settings, run the skill and say
"reconfigure the weekly status for [client]".
