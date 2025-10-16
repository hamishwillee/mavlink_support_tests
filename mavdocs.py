"""
Module imports the ./mavlink/doc/mavlink_xml_to_markdown.py script from the mavlink repo
and uses it to get info about the development.xml dialect.
The data is hard to parse unless you know the format, so this library provides a layer that
gets the information in nested dict, which are easier to parse.

It is intended to use by other scripts that want to run tests on the mavlink library - such as
- convert this incoming ID into an enum value that is human readable
- list all commands.
"""

# Import the docs library to get useful info
import sys
import pprint
import importlib.util
from pathlib import Path


class XMLDialectInfo:
    def __init__(self, dialect="development"):
        # name, type, print_format, xml, description='', enum='', display='', units='', instance=False
        self.name = None
        self.dialect = dialect

        # self.type = None
        # self.units = None

        # Add the directory to the system path
        module_path = Path("./mavlink/doc/mavlink_xml_to_markdown.py").resolve()
        sys.path.append(str(module_path.parent))
        # Import the docs module
        module_name = "mavlink_xml_to_markdown"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        xmldocs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(xmldocs)

        # Now you can use the functions and classes from the imported module
        # module.some_function()
        # print(dir(xmldocs))
        # Access the XMLFiles class directly from the xmldocs object
        XMLFiles = xmldocs.XMLFiles
        #
        print(type(XMLFiles))

        self.files = XMLFiles(
            dialect=self.dialect, source_dir="./mavlink/message_definitions/v1.0/"
        )
        print("DEBUG HERE SELF")
        print(type(self.files))
        self.dict = self.convert_to_dict(self.files)
        print(type(self.dict))

    def convert_to_dict(self, obj):
        if isinstance(obj, dict):
            return {k: self.convert_to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_to_dict(item) for item in obj]
        # This converts mavlink XML doc objects (only) to dicts.
        elif (
            hasattr(obj, "__dict__")
            and obj.__class__.__module__ == "mavlink_xml_to_markdown"
        ):
            return self.convert_to_dict(obj.__dict__)
        else:
            return obj

    def getFiles(self):
        return self.dict["xml_dialects"]

    def getDialect(self):
        return self.dict["xml_dialects"][self.dialect]

    def getMessages(self):
        return self.dict["xml_dialects"][self.dialect]["messages"]

    def getMessage(self, id=None, name=None):
        print(f"debug: getMessage: id:{id} name:{name}")

        if id is None and name is None:
            raise ValueError("Either id or name must be specified")

        if id is not None and name is not None:
            raise ValueError("Only one of id or name must be specified")

        if name is not None:
            return self.dict["xml_dialects"][self.dialect]["messages"][name]
        if id is not None:
            message_by_name_dict = self.dict["xml_dialects"][self.dialect]["messages"]
            message_by_id_dict = {
                value["id"]: value for key, value in message_by_name_dict.items()
            }
            return message_by_id_dict[id]

    def getMessageId(self, name):
        return self.dict["xml_dialects"][self.dialect]["messages"][name]["id"]

    def getMessageName(self, id):
        print(f"debug: getMessageName: {id}")
        return self.getMessage(id=id)["name"]

    def getEnums(self):
        return self.dict["xml_dialects"][self.dialect]["enums"]

    def getEnum(self, name):
        return self.dict["xml_dialects"][self.dialect]["enums"][name]

    def getEnumEntries(self, name):
        """Get enum entries as dict for name, sorted by name"""
        return self.dict["xml_dialects"][self.dialect]["enums"][name]["entries"]


    def getEnumEntriesId(self, name):
        """Get enum entries as dict for name, sorted by id"""
        enum_entries_by_name_dict = self.dict["xml_dialects"][self.dialect]["enums"][
            name
        ]["entries"]
        enum_entries_by_id_dict = {
            value["value"]: value for key, value in enum_entries_by_name_dict.items()
        }
        return enum_entries_by_id_dict

    def getEnumEntryNameFromId(self, enumName, id):
        """Get enum entries name from id"""
        enum_entries_by_id_dict = self.getEnumEntriesId(enumName)
        return enum_entries_by_id_dict[id]["name"]

    def getEnumEntryIdFromName(self, enumName, name):
        """Get enum entries name from id"""
        enum_entries_by_name_dict = self.getEnumEntries(enumName)
        return enum_entries_by_name_dict[name]["value"]

    def getCommands(self):
        print("debug: mavdocs.py: getCommands()")
        return self.dict["xml_dialects"][self.dialect]["commands"]

    def getCommand(self, name):
        return self.dict["xml_dialects"][self.dialect]["commands"][name]

    def getCommandId(self, name):
        # print(f"debug: getCommandId: {name}")
        return self.dict["xml_dialects"][self.dialect]["commands"][name]["value"]

    def getCommandById(self, id):
        # print(f"debug: getCommandById: {id}")
        command_entries_by_name_dict = self.dict["xml_dialects"][self.dialect][
            "commands"
        ]
        command_entries_by_id_dict = {
            value["value"]: value for key, value in command_entries_by_name_dict.items()
        }
        return command_entries_by_id_dict[id]

    def getCommandName(self, id):
        # print(f"debug: getCommandName: {id}")
        return self.getCommandById(id)["name"]


def tests():
    xmlInfo = XMLDialectInfo(dialect="development")
    # commonFiles = xmlInfo.getFiles()

    # print(xmlInfo.getMessages().keys())

    # print(xmlInfo.getMessage('BATTERY_INFO'))

    # dialectThingies  = xmlInfo.getDialect()
    # messages = xmlInfo.getMessages()

    messageid = xmlInfo.getMessageId("PARAM_EXT_REQUEST_READ")
    print(messageid)
    message = xmlInfo.getMessage(id=messageid)
    print(message)
    message = xmlInfo.getMessage(id=messageid)
    message_name = xmlInfo.getMessageName(messageid)
    print(message_name)

    message = coxmlInfommon.getMessage(name="PARAM_EXT_REQUEST_READ")
    print(message)
    # test1 = xmlInfo.getMessage() # should fail

    enums = xmlInfo.getEnums()
    # print(enums)

    enumName = xmlInfo.getEnum("MAV_TYPE")
    pprint.pprint(enumName)

    enumNameEntries = xmlInfo.getEnumEntries("MAV_TYPE")
    pprint.pprint(enumNameEntries)

    enumNameEntriesId = xmlInfo.getEnumEntriesId("MAV_TYPE")
    pprint.pprint(enumNameEntriesId)

    # What is enum 38 in MAV_TYPE
    print(enumNameEntriesId[38]["name"])

    # What is enum 38 in MAV_TYPE
    print(xmlInfo.getEnumEntryNameFromId("MAV_TYPE", 38))

    # commands = xmlInfo.getCommands()
    # print(commands)
    commandByName = xmlInfo.getCommand("MAV_CMD_SPATIAL_USER_2")
    pprint.pprint(commandByName)
    commandIdByName = xmlInfo.getCommandId("MAV_CMD_SPATIAL_USER_2")
    pprint.pprint(commandIdByName)

    commandById = xmlInfo.getCommandById(commandIdByName)
    pprint.pprint(commandById)


"""
for key, value in messages.items():
    print(key)
    #print(value)
#print(commonFiles)
"""


"""

print(f"CF : {type(commonFiles)}")
pprint.pprint(commonFiles)
commonFilesDict = commonFiles.to_dict()
print(f"CF dict: {type(commonFilesDict)}")
pprint.pprint(commonFiles.to_dict())


commonDict = xmlInfo.getDialect()
pprint.pprint(commonDict)
#pprint.pprint(commonDict.to_dict())

commonMessages = xmlInfo.getMessages()
print("getMessages()")
pprint.pprint(commonMessages)
print("getMessages() todict")
#pprint.pprint(commonMessages.to_dict())
for key, value in commonMessages.items():
    print(key)
    print(value)
    print(value.to_dict())

"""

# print(f"type commonDict: {commonDict}")
# print(type(commonDict))
# print(f"commonDict: {commonDict}")
# pprint.pprint(commonDict)
