# MAVLink Support Tests

A set of tests written in Libmav-python that test for things like:
- What messages are streamed by default
- What commands are supported, unsupported, or don't state either


To use:

```
git clone https://github.com/hamishwillee/mavlink_support_tests.git`
cd mavlink_support_tests
pip install -r requirements.txt
git clone https://github.com/mavlink/mavlink.git --recursive #note, needed for getting entities for tests, so must be under mavlink support tests
```


Then modify mavlink\doc\mavlink_xml_to_markdown.py to add this up the top (note the backup folder has a version as example

```
class CommonMethods:

    def to_dict(self):
        return self.__dict__
```

And all the classes to derive from it.

```
class MAVXML(CommonMethods):
```

We should perhaps to this using a decorator :-0


you will also need PX4-Autopilot or something to test against


To run against PX4 in local simulator:

```
python3 libmav_msg_cmd.py
```


## Files

To list

- 