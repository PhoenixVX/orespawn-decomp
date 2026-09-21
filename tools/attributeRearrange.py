import argparse
import struct
import zipfile
import shutil
import hashlib
from os import listdir
from os.path import isfile, join
filename_debug = ""

output_dir = "./orespawn_compiled"
try:
    shutil.rmtree(output_dir)
except FileNotFoundError:
    pass

jar_folder = "../build/libs"
jar = "modid-1.0.jar"

shutil.copyfile(f'{jar_folder}/{jar}', f'./{jar}')

with zipfile.ZipFile(f'./{jar}', 'r') as zip_ref:
    zip_ref.extractall(output_dir)
onlyfiles = [f for f in listdir(join(output_dir, "danger/orespawn")) if isfile(join(join(output_dir, "danger/orespawn", f)))]

class BufferedWriter:
    def __init__(self, filename):
        self.buffer = b''
        self.filename = filename
    def write(self, data):
        self.buffer += data
        if len(self.buffer) > 16384:
            with open(self.filename, 'ab') as f:
                f.write(self.buffer)
            self.buffer = b''
    def close(self):
        if len(self.buffer) > 0:
            with open(self.filename, 'ab') as f:
                f.write(self.buffer)

class SpecialStream:
    def __init__(self, stream):
        self.internal_stream = stream
    def read_s(self, size):
        return int.from_bytes(self.internal_stream.read(size), 'big', signed=True)
    def read_u(self, size):
        return int.from_bytes(self.internal_stream.read(size), 'big', signed=False)

    def read_s8(self):
        return self.read_s(1)
    def read_u8(self):
        return self.read_u(1)

    def read_s16(self):
        return self.read_s(2)
    def read_u16(self):
        return self.read_u(2)

    def read_s32(self):
        return self.read_s(4)
    def read_u32(self):
        return self.read_u(4)

    def read_s64(self):
        return self.read_s(8)
    def read_u64(self):
        return self.read_u(8)
    
    def read_float(self):
        return struct.unpack('>f', self.internal_stream.read(4))[0]
    def read_double(self):
        return struct.unpack('>d', self.internal_stream.read(8))[0]

    def read_string(self):
        string_size = self.read_u16()
        return self.internal_stream.read(string_size).decode('utf-8')
class S32:
    def __init__(self, stream):
        self.value = stream.read_s32()
    def get_type(self):
        return "Integer"
    def save(self, stream):
        stream.write(b'\x03')
        stream.write((self.value & 0xFFFFFFFF).to_bytes(4,'big'))
    def __str__(self):
        return str(self.value)

class Float:
    def __init__(self, stream):
        self.value = stream.read_float()
    def get_type(self):
        return "Float"
    def save(self, stream):
        stream.write(b'\x04')
        stream.write(struct.pack('>f', self.value))
    def __str__(self):
        return str(self.value) + 'f'

class S64:
    def __init__(self, stream):
        self.value = stream.read_s64()
    def get_type(self):
        return "Long"
    def save(self, stream):
        stream.write(b'\x05')
        stream.write((self.value & 0xFFFFFFFFFFFF).to_bytes(8,'big'))
    def __str__(self):
        return str(self.value) + 'l'

class Double:
    def __init__(self, stream):
        self.value = stream.read_double()
    def save(self, stream):
        stream.write(b'\x06')
        stream.write(struct.pack('>d', self.value))
    def __str__(self):
        return str(self.value) + 'd'

class ClassRef:
    def __init__(self, clazz, stream):
        self.clazz = clazz
        self.index = stream.read_u16()
    def get_type(self):
        return "Class"
    def save(self, stream):
        stream.write(b'\x07')
        stream.write(self.index.to_bytes(2,'big'))
    def __str__(self):
        return str(self.clazz.constant_pool[self.index-1])

class StringRef:
    def __init__(self, clazz, stream):
        self.clazz = clazz
        self.index = stream.read_u16()
    def get_type(self):
        return "String"
    def save(self, stream):
        stream.write(b'\x08')
        stream.write(self.index.to_bytes(2,'big'))
    def __str__(self):
        return str(self.clazz.constant_pool[self.index-1])

class FieldRef:
    def __init__(self, clazz, stream):
        self.clazz = clazz
        self.class_index = stream.read_u16()
        self.descriptor_index = stream.read_u16()
    def get_type(self):
        return "Fieldref"
    def save(self, stream):
        stream.write(b'\x09')
        stream.write(self.class_index.to_bytes(2,'big'))
        stream.write(self.descriptor_index.to_bytes(2,'big'))
    def __str__(self):
        return f'{str(self.clazz.constant_pool[self.class_index-1])}.{str(self.clazz.constant_pool[self.descriptor_index-1])}'

class MethodRef:
    def __init__(self, clazz, stream):
        self.clazz = clazz
        self.class_index = stream.read_u16()
        self.descriptor_index = stream.read_u16()
    def get_type(self):
        return "Methodref"
    def save(self, stream):
        stream.write(b'\x0A')
        stream.write(self.class_index.to_bytes(2,'big'))
        stream.write(self.descriptor_index.to_bytes(2,'big'))
    def __str__(self):
        return f'{str(self.clazz.constant_pool[self.class_index-1])}."{str(self.clazz.constant_pool[self.descriptor_index-1])}"'

class InterfaceRef:
    def __init__(self, clazz, stream):
        self.clazz = clazz
        self.class_index = stream.read_u16()
        self.descriptor_index = stream.read_u16()
    def get_type(self):
        return "InterfaceMethodref"
    def save(self, stream):
        stream.write(b'\x0B')
        stream.write(self.class_index.to_bytes(2,'big'))
        stream.write(self.descriptor_index.to_bytes(2,'big'))
    def __str__(self):
        return f'{str(self.clazz.constant_pool[self.class_index-1])}."{str(self.clazz.constant_pool[self.descriptor_index-1])}"'

class Descriptor:
    def __init__(self, clazz, stream):
        self.clazz = clazz
        self.name_index = stream.read_u16()
        self.type_index = stream.read_u16()
    def get_type(self):
        return "NameAndType"
    def save(self, stream):
        stream.write(b'\x0C')
        stream.write(self.name_index.to_bytes(2,'big'))
        stream.write(self.type_index.to_bytes(2,'big'))
    def __str__(self):
        name = str(self.clazz.constant_pool[self.name_index-1])
        if '<' in name or '>' in name:
            name = f'"{name}"'
        return f'{name}:{str(self.clazz.constant_pool[self.type_index-1])}'

class CodeAttribute:
    def __init__(self, clazz, stream):
        self.clazz = clazz
        self.max_stack = stream.read_u16()
        self.max_locals = stream.read_u16()
        self.code_length = stream.read_u32()
        self.code = stream.internal_stream.read(self.code_length)
        self.exception_table_length = stream.read_u16()
        self.exception_table = stream.internal_stream.read(self.exception_table_length * 8)
        self.attributes_count = stream.read_u16()
        self.attributes = []
        for i in range(0, self.attributes_count):
            self.attributes.append(AttributeInfo(clazz, stream))
    def save(self, stream):
        stream.write(self.max_stack.to_bytes(2, 'big'))
        stream.write(self.max_locals.to_bytes(2, 'big'))
        stream.write(self.code_length.to_bytes(4, 'big'))
        stream.write(self.code)
        stream.write(self.exception_table_length.to_bytes(2, 'big'))
        stream.write(self.exception_table)
        self.attributes = rearrange_attributes(self.attributes, self.clazz.indexes)
        stream.write(len(self.attributes).to_bytes(2, 'big'))
        for attribute in self.attributes:
            attribute.save(stream)

class AttributeInfo:
    def __init__(self, clazz, stream):
        self.clazz = clazz
        self.attribute_name = str(self.clazz.constant_pool[stream.read_u16()-1])
        self.attribute_length = stream.read_u32()
        match self.attribute_name:
            case "Code":
                self.info = CodeAttribute(clazz, stream)
            case _:
                self.info = stream.internal_stream.read(self.attribute_length)
    def save(self, stream):
        global filename_debug
        stream.write(self.clazz.new_indexes[self.attribute_name].to_bytes(2, 'big'))
        stream.write((self.attribute_length & 0xFFFFFFFF).to_bytes(4, 'big'))
        if type(self.info) is CodeAttribute:
            self.info.save(stream)
        else:
            stream.write(self.info)

class FieldInfo:
    def __init__(self, clazz, stream):
        self.clazz = clazz
        self.access_flags = stream.read_u16()
        self.name_index = stream.read_u16()
        self.descriptor_index = stream.read_u16()
        self.attributes_count = stream.read_u16()
        self.attributes = []
        for i in range(0, self.attributes_count):
            self.attributes.append(AttributeInfo(clazz, stream))
    def save(self, stream):
        stream.write(self.access_flags.to_bytes(2, 'big'))
        stream.write(self.name_index.to_bytes(2, 'big'))
        stream.write(self.descriptor_index.to_bytes(2, 'big'))
        self.attributes = rearrange_attributes(self.attributes, self.clazz.indexes)
        stream.write(len(self.attributes).to_bytes(2, 'big'))
        for attribute in self.attributes:
            attribute.save(stream)

class MethodInfo:
    def __init__(self, clazz, stream):
        self.clazz = clazz
        self.access_flags = stream.read_u16()
        self.name_index = stream.read_u16()
        self.descriptor_index = stream.read_u16()
        self.attributes_count = stream.read_u16()
        self.attributes = []
        for i in range(0, self.attributes_count):
            self.attributes.append(AttributeInfo(clazz, stream))
    def save(self, stream):
        stream.write(self.access_flags.to_bytes(2, 'big'))
        stream.write(self.name_index.to_bytes(2, 'big'))
        stream.write(self.descriptor_index.to_bytes(2, 'big'))
        self.attributes = rearrange_attributes(self.attributes, self.clazz.indexes)
        stream.write(len(self.attributes).to_bytes(2, 'big'))
        for attribute in self.attributes:
            attribute.save(stream)

class String:
    def __init__(self, stream):
        self.value = stream.read_string()
    def get_type(self):
        return "Utf8"
    def save(self, stream):
        stream.write(b'\x01')
        byt = self.value.encode('utf-8')
        stream.write(len(byt).to_bytes(2,'big'))
        stream.write(byt)
    def __str__(self):
        return self.value

different = {
    "AntBlock.class": {
        "ConstantValue": 0,
        "RuntimeVisibleAnnotations": 0,
        "Code": 0,
        "LocalVariableTable": 0,
        "LineNumberTable": 0,
        "StackMapTable": 0,
        "Signature": 0,
        "SourceFile": 0,
        "EnclosingMethod": 0,
        "InnerClasses": 0,
    },
    "AntRobot.class": {
        "Code": 0,
        "LocalVariableTable": 0,
        "LineNumberTable": 0,
        "StackMapTable": 0,
        "RuntimeVisibleAnnotations": 0,
        "SourceFile": 0,
        "InnerClasses": 0
    },
    "CrystalFurnaceGUI.class": {
        "Code": 0,
        "LocalVariableTable": 0,
        "LineNumberTable": 0,
        "StackMapTable": 0,
        "Signature": 0,
        "SourceFile": 0,
        "InnerClasses": 0,
        "RuntimeVisibleAnnotations": 0,
    },
}
different["BlockButterflyPlant.class"] = different['AntBlock.class']
different["Bertha.class"] = different['AntRobot.class']
different["BigHammer.class"] = different['AntRobot.class']
different["BlockAppleLeaves.class"] = different['AntRobot.class']
different["BlockCorn.class"] = different['AntRobot.class']
different["BlockCrystalLeaves.class"] = different['AntRobot.class']
different["BlockCrystalPlant.class"] = different['AntRobot.class']
different["BlockCrystalTorch.class"] = different['AntRobot.class']
different["BlockCrystalTreeLog.class"] = different['AntBlock.class']
different["BlockDuctTape.class"] = different['AntBlock.class']
different["BlockDuplicatorLog.class"] = different['AntRobot.class']
different["BlockExperienceLeaves.class"] = different['AntRobot.class']
different["BlockExperiencePlant.class"] = different['AntRobot.class']
different["BlockExtremeTorch.class"] = different['AntRobot.class']
different["BlockFireflyPlant.class"] = different['AntBlock.class']
different["BlockLettuce.class"] = different['AntRobot.class']
different["BlockMosquitoPlant.class"] = different['AntBlock.class']
different["BlockMothPlant.class"] = different['AntBlock.class']
different["BlockPizza.class"] = different['AntBlock.class']
different["BlockQuinoa.class"] = different['AntRobot.class']
different["BlockRadish.class"] = different['AntRobot.class']
different["BlockRice.class"] = different['AntRobot.class']
different["BlockRuby.class"] = different['AntRobot.class']
different["BlockScaryLeaves.class"] = different['AntRobot.class']
different["BlockSkyTreeLog.class"] = different['AntRobot.class']
different["BlockStrawberry.class"] = different['AntRobot.class']
different["BlockTitanium.class"] = different['AntRobot.class']
different["BlockTomato.class"] = different['AntRobot.class']
different["BlockUranium.class"] = different['AntRobot.class']
different["Cephadrome.class"] = different['AntRobot.class']
different["ContainerCrystalFurnace.class"] = different['AntRobot.class']
different["CreeperRepellent.class"] = different['AntRobot.class']
different["CritterCage.class"] = different['AntRobot.class']
different["CrystalAntBlock.class"] = different['AntBlock.class']
different["CrystalFurnace.class"] = different['AntBlock.class']
different["CrystalGrass.class"] = different['AntBlock.class']
different["CrystalShovel.class"] = different['AntRobot.class']
different["CrystalWorkbench.class"] = different['AntBlock.class']
different["CrystalWorkbenchGUI.class"] = different['CrystalFurnaceGUI.class']
different["Dragon.class"] = different['AntRobot.class']
different["DungeonSpawnerBlock.class"] = different['AntRobot.class']
different["Elevator.class"] = different['AntRobot.class']
different["EmeraldPickaxe.class"] = different['AntRobot.class']
different["ExperienceCatcher.class"] = different['AntRobot.class']
different["ExperienceSword.class"] = different['AntRobot.class']
different["FairySword.class"] = different['AntRobot.class']
different["GirlfriendOverlayGui.class"] = different['AntRobot.class']
different["GodzillaHead.class"] = different['AntRobot.class']
different["InstantGarden.class"] = different['AntRobot.class']
different["InstantShelter.class"] = different['AntRobot.class']
different["IslandBlock.class"] = different['AntRobot.class']
different["ItemAcid.class"] = different['AntRobot.class']
different["ItemAppleSeed.class"] = different['AntRobot.class']
different["ItemCreeperLauncher.class"] = different['AntRobot.class']
different["ItemDuctTape.class"] = different['AntRobot.class']
different["ItemElevator.class"] = different['AntRobot.class']
different["ItemExperienceTreeSeed.class"] = different['AntRobot.class']
different["ItemFireFish.class"] = different['AntRobot.class']
different["ItemGenericFish.class"] = different['AntRobot.class']
different["ItemIceBall.class"] = different['AntRobot.class']
different["ItemIrukandji.class"] = different['AntRobot.class']
different["ItemLaserBall.class"] = different['AntRobot.class']
different["ItemLavaEel.class"] = different['AntRobot.class']
different["ItemMagicApple.class"] = different['AntRobot.class']
different["ItemMinersDream.class"] = different['AntRobot.class']
different["ItemNetherLost.class"] = different['AntRobot.class']
different["ItemOreSpawnArmor.class"] = different['AntRobot.class']
different["ItemPizza.class"] = different['AntRobot.class']
different["ItemRandomDungeon.class"] = different['AntRobot.class']
different["ItemRayGun.class"] = different['AntRobot.class']
different["ItemRock.class"] = different['AntRobot.class']
different["ItemShoes.class"] = different['AntRobot.class']
different["ItemSifter.class"] = different['AntRobot.class']
different["ItemSparkFish.class"] = different['AntRobot.class']
different["ItemSpawnEgg.class"] = different['AntRobot.class']
different["ItemSpiderRobotKit.class"] = different['AntRobot.class']
different["ItemSquidZooka.class"] = different['AntRobot.class']
different["ItemSunFish.class"] = different['AntRobot.class']
different["ItemSunspotUrchin.class"] = different['AntRobot.class']
different["ItemThunderStaff.class"] = different['AntRobot.class']
different["ItemWaterBall.class"] = different['AntRobot.class']
different["ItemWrench.class"] = different['AntRobot.class']
different["ItemZooKeeper.class"] = different['AntRobot.class']
different["KingHead.class"] = different['AntRobot.class']
different["KingSpawnerBlock.class"] = different['AntRobot.class']
different["KrakenRepellent.class"] = different['AntRobot.class']
different["Lavafoam.class"] = different['AntRobot.class']
different["Leon.class"] = different['AntRobot.class']
different["MantisClaw.class"] = different['AntRobot.class']
different["MoleDirtBlock.class"] = different['AntRobot.class']
different["MyBlockFlower.class"] = different['AntRobot.class']
different["NightmareSword.class"] = different['AntRobot.class']
different["OreBasicStone.class"] = different['AntRobot.class']
different["OreCrystal.class"] = different['AntRobot.class']
different["OreCrystalCrystal.class"] = different['AntRobot.class']
different["OreGenericEgg.class"] = different['AntRobot.class']
different["OreSalt.class"] = different['AntRobot.class']
different["OreSpawnMain.class"] = different['AntBlock.class']
different["OreTitanium.class"] = different['AntRobot.class']
different["OreUranium.class"] = different['AntRobot.class']
different["Ostrich.class"] = different['AntRobot.class']
different["PoisonSword.class"] = different['AntRobot.class']
different["QueenHead.class"] = different['AntRobot.class']
different["QueenSpawnerBlock.class"] = different['AntRobot.class']
different["RatSword.class"] = different['AntRobot.class']
different["RenderElevator.class"] = different['CrystalFurnaceGUI.class']
different["RenderSpinner.class"] = different['CrystalFurnaceGUI.class']
different["RenderThrownRock.class"] = different['CrystalFurnaceGUI.class']
different["RiderControl.class"] = different['AntRobot.class']
different["RiderControlMessageHandler.class"] = different['CrystalFurnaceGUI.class']
different["RTPBlock.class"] = different['AntRobot.class']
different["SkateBow.class"] = different['AntRobot.class']
different["Slice.class"] = different['AntRobot.class']
different["SpiderRobot.class"] = different['AntRobot.class']
different["StepAccross.class"] = different['AntRobot.class']
different["StepDown.class"] = different['AntRobot.class']
different["StepUp.class"] = different['AntRobot.class']
different["TheKing.class"] = different['AntRobot.class']
different["ThePrinceAdult.class"] = different['AntRobot.class']
different["ThePrinceTeen.class"] = different['AntRobot.class']
different["TheQueen.class"] = different['AntRobot.class']
different["TileEntityCrystalFurnace.class"] = different['AntRobot.class']
different["UltimateAxe.class"] = different['AntRobot.class']
different["UltimateBow.class"] = different['AntRobot.class']
different["UltimateFishHook.class"] = different['AntBlock.class']
different["UltimateFishingRod.class"] = different['AntRobot.class']
different["UltimateHoe.class"] = different['AntRobot.class']
different["UltimatePickaxe.class"] = different['AntRobot.class']
different["UltimateShovel.class"] = different['AntRobot.class']
different["UltimateSword.class"] = different['AntRobot.class']
different["ZooCage.class"] = different['AntRobot.class']

def rearrange_attributes(tbl, arrangement):
    new_tbl = []
    RuntimeVisibleAnnotations = None
    for name, index in arrangement.items():
        for attribute in tbl:
            if attribute.attribute_name == "RuntimeVisibleAnnotations":
                RuntimeVisibleAnnotations = attribute
                break
            elif attribute.attribute_name == name:
                new_tbl.append(attribute)
                break
    if not RuntimeVisibleAnnotations is None:
        new_tbl.append(RuntimeVisibleAnnotations)
    new_tbl3 = [x.attribute_name for x in new_tbl]
    return new_tbl

class ClassFile:
    def __init__(self, stream):
        assert stream.internal_stream.read(4) == b'\xCA\xFE\xBA\xBE'
        self.minor_version = stream.read_u16()
        self.major_version = stream.read_u16()
        self.constant_pool_count = stream.read_u16()
        self.constant_pool = []
        i = 1
        while i < self.constant_pool_count:
            tag = stream.read_u8()
            data = None
            match tag:
                case 1:
                    data = String(stream)
                case 3:
                    data = S32(stream)
                case 4:
                    data = Float(stream)
                case 5:
                    data = S64(stream)
                    self.constant_pool.append(None)
                    i+=1
                case 6:
                    data = Double(stream)
                    self.constant_pool.append(None)
                    i+=1
                case 7:
                    data = ClassRef(self, stream)
                case 8:
                    data = StringRef(self, stream)
                case 9:
                    data = FieldRef(self, stream)
                case 10:
                    data = MethodRef(self, stream)
                case 11:
                    data = InterfaceRef(self, stream)
                case 12:
                    data = Descriptor(self, stream)
                case _:
                    print(f"UNKNOWN CONST TYPE: {tag} @ {i} CONST_POOL_SIZE: {self.constant_pool_count}")
                    exit()
            i+=1
            self.constant_pool.append(data)
        self.access_flags = stream.read_u16()
        self.this_class = stream.read_u16()
        self.super_class = stream.read_u16()
        self.interfaces_count = stream.read_u16()
        self.interfaces = []
        for i in range(0, self.interfaces_count):
            self.interfaces.append(stream.read_u16())
        self.fields_count = stream.read_u16()
        self.fields = []
        for i in range(0, self.fields_count):
            self.fields.append(FieldInfo(self, stream))
        self.methods_count = stream.read_u16()
        self.methods = []
        for i in range(0, self.methods_count):
            self.methods.append(MethodInfo(self, stream))
        self.attributes_count = stream.read_u16()
        self.attributes = []
        for i in range(0, self.attributes_count):
            self.attributes.append(AttributeInfo(self, stream))
    def save(self, stream, filename):
        stream.write(b'\xCA\xFE\xBA\xBE')
        stream.write(self.minor_version.to_bytes(2, 'big'))
        stream.write(self.major_version.to_bytes(2, 'big'))
        stream.write((len(self.constant_pool)+1).to_bytes(2, 'big'))
        if filename in different:
            self.indexes = different[filename].copy()
        else:
            self.indexes = {
                "ConstantValue": 0,
                "Code": 0,
                "LocalVariableTable": 0,
                "LineNumberTable": 0,
                "RuntimeVisibleAnnotations": 0,
                "StackMapTable": 0,
                "Signature": 0,
                "SourceFile": 0,
                "EnclosingMethod": 0,
                "InnerClasses": 0,
            }
        is_attributestuff = False
        for i, constant in enumerate(self.constant_pool):
            if not is_attributestuff:
                if type(constant) is String:
                    if constant.value in self.indexes:
                        is_attributestuff = True
            if is_attributestuff:
                if constant.value in self.indexes:
                    self.indexes[constant.value] = i+1
        for name, index in self.indexes.items():
            if index == 0:
                continue
            assert name == str(self.constant_pool[index-1])
        min_index = 9999999
        for name, index in self.indexes.items():
            if index != 0 and min_index > index:
                min_index = index
        for i, constant in enumerate(self.constant_pool):
            if i == min_index - 1:
                break
            if constant is None:
                continue
            constant.save(stream)
        if filename in different:
            self.new_indexes = different[filename].copy()
        else:
            self.new_indexes = {
                "ConstantValue": 0,
                "Code": 0,
                "LocalVariableTable": 0,
                "LineNumberTable": 0,
                "RuntimeVisibleAnnotations": 0,
                "StackMapTable": 0,
                "Signature": 0,
                "SourceFile": 0,
                "EnclosingMethod": 0,
                "InnerClasses": 0,
            }
        attr_index = min_index
        for name, index in self.indexes.items():
            if index != 0:
                self.constant_pool[index-1].save(stream)
                self.new_indexes[name] = attr_index
                attr_index+=1
        stream.write(self.access_flags.to_bytes(2, 'big'))
        stream.write(self.this_class.to_bytes(2, 'big'))
        stream.write(self.super_class.to_bytes(2, 'big'))
        stream.write(self.interfaces_count.to_bytes(2, 'big'))
        for interface in self.interfaces:
            stream.write(interface.to_bytes(2, 'big'))
        stream.write(self.fields_count.to_bytes(2, 'big'))
        for field in self.fields:
            field.save(stream)
        stream.write(self.methods_count.to_bytes(2, 'big'))
        for method in self.methods:
            method.save(stream)
        self.attributes = rearrange_attributes(self.attributes, self.indexes)
        stream.write(len(self.attributes).to_bytes(2, 'big'))
        for attribute in self.attributes:
            attribute.save(stream)
match_count = 0
for filename in onlyfiles:
    filename_debug = filename
    clazz = None
    with open(f'{output_dir}/danger/orespawn/{filename}', 'rb') as f:
        clazz = ClassFile(SpecialStream(f))

    with open(f'{output_dir}/danger/orespawn/{filename}', 'wb+') as f:
        pass
    writer = BufferedWriter(f'{output_dir}/danger/orespawn/{filename}')
    clazz.save(writer, filename)
    writer.close()
    hash1 = ""
    hash2 = ""
    with open(f'danger/orespawn/{filename}', 'rb') as f:
        hash1 = hashlib.md5(f.read()).hexdigest()
    with open(join(output_dir, f'danger/orespawn/{filename}'), 'rb') as f:
        hash2 = hashlib.md5(f.read()).hexdigest()
    shouldPrintMatches = False
    if hash1 != hash2:
        print(f'{filename} NONMATCHING')
    else:
        match_count+=1
        if shouldPrintMatches:
            print(f'{filename} MATCHING')

print(f"MATCH %: {(match_count/len(onlyfiles))*100}%")