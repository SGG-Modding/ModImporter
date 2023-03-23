# Mod Importer for SuperGiant Games' Games

import argparse
import logging
import os
import platform
import sys
from collections import defaultdict
from collections import deque
from pathlib import Path

import logging
from collections import OrderedDict
from shutil import copyfile
from datetime import datetime

import csv
import xml.etree.ElementTree as xml

import json

# Logging configuration
logging.basicConfig(
    format='%(message)s',
    handlers=[
        logging.FileHandler("modimporter.log.txt", mode='w'),
        logging.StreamHandler(),
    ],
)
LOGGER = logging.getLogger('modimporter')
LOGGER.setLevel(logging.INFO)

can_mapper = False
try:
    import mapper
    can_mapper = True
except ModuleNotFoundError:
    LOGGER.error("Mapper python module not found! Map changes will be skipped!")
    LOGGER.error("Mapper module should be available in the same place as the importer\n")
can_sjson = False
try:
    import sjson
    can_sjson = True
except ModuleNotFoundError:
    LOGGER.error("SJSON python module not found! SJSON changes will be skipped!")
    LOGGER.error("SJSON module should be available in the same place as the importer\n")


# if we are on MacOS and running PyInstaller executable, force working directory
# to be the one containing the executable
# this is a kludge around MacOS calling executables from the user home rather
# than the current directory when double-clicked on from Finder
# has to be done here due to the rest of the script mixing in `os.path` and
# `pathlib` operations outside of the actual `__main__`
if platform.system() == 'Darwin' and getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    parent_dir = Path(sys.argv[0]).parent
    os.chdir(parent_dir)
    LOGGER.info(f"Running MacOS executable from Finder: forced working directory to {parent_dir}")


## Global Settings

clean_only = False #uninstall option, ignores mod folder

game_aliases = {"Resources":"Hades", #alias for temporary mac support
                "Content":"Hades", #alias for temporary windows store support
                "romfs":"Hades"}  #alias for temporary nintendo switch support

modsdir = "Mods"
modsrel = ".."
gamerel = ".."
scope = "Content"
bakdir = "Backup"
baktype = ""
modfile = "modfile.txt"
mlcom_start = "-:"
mlcom_end = ":-"
comment = "::"
linebreak = ";"
delimiter = ","

modified = "MODIFIED"
modified_modrep = " by Mod Importer @ "
modified_lua = "-- "+modified+" "
modified_xml = "<!-- "+modified+" -->"
modified_sjson = "/* "+modified+" */"
modified_csv = modified
modified_map = modified

default_to = {"Hades":["Scripts/RoomManager.lua"],
            "Pyre":["Scripts/Campaign.lua","Scripts/MPScripts.lua"],
            "Transistor":["Scripts/AllCampaignScripts.txt"]}
default_priority = 100

kwrd_to = ["To"]
kwrd_load = ["Load"]
kwrd_priority = ["Priority"]
kwrd_include = ["Include"]
kwrd_import = ["Import"]
kwrd_topimport = ["Top","Import"]
kwrd_xml = ["XML"]
kwrd_sjson = ["SJSON"]
kwrd_replace = ["Replace"]
kwrd_csv = ["CSV"]
kwrd_map = ["Map"]

reserved_sequence = "_sequence"
reserved_append = "_append"
reserved_replace = "_replace"
reserved_delete = "_delete"
reserved_search = "_search"

## Data Functionality

DNE = ()

def safeget(data,key):
    if isinstance(data,list):
        if isinstance(key,int):
            if key < len(data) and key >= 0:
                return data[key]
        return DNE
    if isinstance(data,OrderedDict):
        return data.get(key,DNE)
    if isinstance(data,xml.ElementTree):
        root = data.getroot()
        if root:
            return root.get(key,DNE)
    if isinstance(data,xml.Element):
        return data.get(key,DNE)
    return DNE

def safepairs(data):
    it = DNE
    if isinstance(data,list):
        it = enumerate(data)
    if isinstance(data,OrderedDict):
        it = data.items()
    return it

def clearDNE(data):
    if isinstance(data,OrderedDict):
        for k,v in data.copy().items():
            if v is DNE:
                del data[k]
                continue
            data[k] = clearDNE(v)
    if isinstance(data,list):
        L = []
        for i,v in enumerate(data):
            if v is DNE:
                continue
            L.append(clearDNE(v))
        data = L
    return data

### LUA import statement adding

def addimport(base,path):
    with open(base,'a',encoding='utf-8') as basefile:
        basefile.write("\nImport "+"\""+modsrel+"/"+path+"\"")

def addtopimport(base,path):
    with open(base,'r+',encoding='utf-8') as basefile:
        lines = basefile.readlines()     
        lines.insert(0, "Import "+"\""+modsrel+"/"+path+"\"\n")  
        basefile.seek(0)                 
        basefile.truncate()
        basefile.writelines(lines)

### CSV mapping

def readcsv(filename):
    with open(filename,'r',newline='',encoding='utf-8-sig') as file:
        return list(csv.reader(file))
    

def writecsv(filename,content):
    with open(filename,'w',newline='',encoding='utf-8-sig') as file:
        writer = csv.writer(file,quoting=csv.QUOTE_MINIMAL)
        for row in content:
            writer.writerow(row)

def csvmap(indata,mapdata):
    target = [0,0]
    current = [0,0]
    append = False
    replace = False
    for row in mapdata:
        if len(row) == 2 and row[0][0] == '<' and row[-1][-1] == '>':
            target[0] = int(row[0][1:])
            target[1] = int(row[-1][:-1])
            current[0] = target[0]
            append = False
            replace = False
            continue
        if len(row) == 1 and row[0] == reserved_append:
            append = True
            replace = False
        if len(row) == 1 and row[0] == reserved_replace:
            append = False
            replace = True
        if append:
            indata.append(row)
        else:
            if replace:
                indata[current[0]]=row
            else:
                current[1] = target[1]
                for value in row:
                    if value == reserved_delete:
                        indata[current[0]][current[1]] = ""
                    elif value != "":
                        indata[current[0]][current[1]] = value
                    current[1] += 1
            current[0] += 1
    return indata
            

def mergecsv(infile,mapfile):
    indata = readcsv(infile)
    if mapfile:
        mapdata = readcsv(mapfile)
    else:
        mapdata = DNE
    indata = csvmap(indata,mapdata)
    writecsv(infile,indata)

### XML mapping

def readxml(filename):
    try:
        return xml.parse(filename)
    except xml.ParseError:
        return DNE

def writexml(filename,content,start=None):
    if not isinstance(filename,str):
        return
    if not isinstance(content, xml.ElementTree):
        return
    content.write(filename)

    #indentation styling
    data = ""
    if start:
        data = start
    with open(filename,'r',encoding='utf-8-sig') as file:
        i = 0
        for line in file:
            nl = False
            if len(line.replace('\t','').replace(' ',''))>1:
                q=True
                p=''
                for s in line:
                    if s == '\"':
                        q = not q
                    if p == '<' and q:
                        if s == '/':
                            i-=1
                            data = data[:-1]
                        else:
                            i+=1
                        data+=p
                    if s == '>' and p == '/' and q:
                        i-=1
                    if p in (' ') or (s=='>' and p == '\"') and q:
                        data+='\n'+'\t'*(i-(s=='/'))
                    if s not in (' ','\t','<') or not q:
                        data+=s
                    p=s
    open(filename,'w',encoding='utf-8').write(data)

def xmlmap(indata,mapdata):
    if mapdata is DNE:
        return indata
    if type(indata)==type(mapdata):
        if isinstance(mapdata,dict):
            for k,v in mapdata.items():
                indata[k] = xmlmap(indata.get(k),v)
            return indata
        if isinstance(mapdata,xml.ElementTree):
            root = xmlmap(indata.getroot(),mapdata.getroot())
            if root:
                indata._setroot(root)
            return indata
        elif isinstance(mapdata,xml.Element):
            mtags = dict()
            for v in mapdata:
                if not mtags.get(v.tag,False):
                    mtags[v.tag]=True
            for tag in mtags:
                mes = mapdata.findall(tag)
                ies = indata.findall(tag)
                for i,me in enumerate(mes):
                    ie = safeget(ies,i)
                    if ie is DNE:
                        indata.append(me)
                        continue
                    if me.get(reserved_delete,None) not in (None,'0','false','False'):
                        indata.remove(ie)
                        continue
                    if me.get(reserved_replace,None) not in (None,'0','false','False'):
                        ie.text = me.text
                        ie.tail = me.tail
                        ie.attrib = me.attrib
                        del ie.attrib[reserved_replace]
                        continue
                    ie.text = xmlmap(ie.text,me.text)
                    ie.tail = xmlmap(ie.tail,me.tail)
                    ie.attrib = xmlmap(ie.attrib,me.attrib)
                    xmlmap(ie,me)
            return indata
        return mapdata
    else:
        return mapdata
    return mapdata

def mergexml(infile,mapfile):
    start = ""
    with open(infile,'r',encoding='utf-8-sig') as file:
        for line in file:
            if line[:5] == "<?xml" and line[-3:] == "?>\n":                
                start = line
                break
    indata = readxml(infile)
    if mapfile:
        mapdata = readxml(mapfile)
    else:
        mapdata = DNE
    indata = xmlmap(indata,mapdata)
    writexml(infile,indata,start)


### Map Binaries mapping

if can_mapper:
    def cachemapchange(cache, mapfile):
        map_json = []
        with open(mapfile, "r") as f:
            map_json = json.load(f)
            
        if reserved_append in map_json:
            if reserved_append not in cache:
                cache[reserved_append] = []
            
            for json_dict in  map_json[reserved_append]:
                cache[reserved_append].append(json_dict)

        if reserved_delete in map_json:
            if reserved_delete not in cache:
                cache[reserved_delete] = []
            
            #merge delete values into the cache[reserved_delete]
            for id in  map_json[reserved_delete]:
                if id not in cache[reserved_delete]:
                    cache[reserved_delete].append(id)

        if reserved_replace in map_json:
            if reserved_replace not in cache:
                cache[reserved_replace] = {}
            
            #merge replace values into the cache[reserved_replace]
            for json_dict in  map_json[reserved_replace]:
                id = json_dict["Id"]

                if not id in cache[reserved_replace]:
                    cache[reserved_replace][id] = {}

                for key in json_dict:
                    if key == "Id":
                        continue
                    value = json_dict[key]

                    cache[reserved_replace][id][key] = value

    def findjsonindex(id, json):
        count = 0
        for json_dict in json:
            if json_dict["Id"] == id:
                return count
            count = count + 1
        
        return -1

    def changemap(infile, mapchanges):
        in_json = mapper.DecodeBinaries(infile)
        
        if reserved_append in mapchanges:
            for json_dict in mapchanges[reserved_append]:
                    in_json.append(json_dict)

        if reserved_delete in mapchanges:
            for id in mapchanges[reserved_delete]:
                json_id = findjsonindex(id, in_json)
                if json_id >= 0:
                    del in_json[json_id] 

        if reserved_replace in mapchanges:
            for id in mapchanges[reserved_replace]:
                changes = mapchanges[reserved_replace][id]
                
                json_id = findjsonindex(id, in_json)

                if json_id == -1:
                    LOGGER.error("Cannot find", id, "in map file", infile, "when trying to replace values")
                for key in changes:
                    value = changes[key]

                    in_json[json_id][key] = value
                id = ""

        map_binaries = mapper.EncodeBinaries(in_json)

        with open(infile, "wb") as f:
            f.write(map_binaries) 

### SJSON mapping

if can_sjson:
    def readsjson(filename):
        try:
            return sjson.loads(open(filename,'r',encoding='utf-8-sig').read())
        except sjson.ParseException as e:
            LOGGER.error(repr(e))
            return DNE

    def writesjson(filename,content):
        if not isinstance(filename,str):
            return
        if isinstance(content,OrderedDict):
            content = sjson.dumps(content, 2)
        else:
            content = ""
        with open(filename,'w',encoding='utf-8') as f:
            f.write(content)

    def sjsonsearch(indata,queries):
        def pred(dat,mat):
            if (it := safepairs(mat)) is not DNE:
                return all(pred(dat[k],v) for k,v in it)
            return dat == mat
        for matdata,mapdata in queries:
            for k,v in ((k,v) for k,v in safepairs(indata) if pred(v,matdata)):
                indata[k] = sjsonmap(v,mapdata)
        return indata


    def sjsonmap(indata,mapdata):
        if mapdata is DNE:
            return indata
        elif mapdata==reserved_delete:
            return DNE
        elif safeget(mapdata,reserved_sequence):
            S = []
            for k,v in mapdata.items():
                try:
                    d = int(k)-len(S)
                    if d>=0:
                        S.extend([DNE]*(d+1))
                    S[int(k)]=v
                except ValueError:
                    continue
            mapdata = S
        if type(indata)==type(mapdata):
            if isinstance(mapdata,list) and safeget(mapdata,0) == reserved_append:
                for i in range(1,len(mapdata)):
                    indata.append(mapdata[i])
                return indata
            if isinstance(mapdata,list):
                if safeget(mapdata,0)==reserved_search:
                    search = mapdata[1]
                    return sjsonsearch(indata,zip(search[::2],search[1::2]))
                if safeget(mapdata,0)==reserved_replace:
                    del mapdata[0]
                    return mapdata
                indata.extend([DNE]*(len(mapdata)-len(indata)))
            elif isinstance(mapdata,dict):
                if search := safeget(mapdata,reserved_search):
                    return sjsonsearch(indata,zip(search[::2],search[1::2]))
                if safeget(mapdata,reserved_replace):
                    del mapdata[reserved_replace]
                    return mapdata
            if (it := safepairs(mapdata)) is not DNE:
                for k,v in it:
                    indata[k] = sjsonmap(safeget(indata,k),v)
                return indata
        return mapdata
        
    def mergesjson(infile,mapfile):
        indata = readsjson(infile)
        if mapfile:
            mapdata = readsjson(mapfile)
        else:
            mapdata = DNE
        indata = sjsonmap(indata,mapdata)
        indata = clearDNE(indata)
        writesjson(infile,indata)

## FILE/MOD CONTROL

mode_lua = 1
mode_lua_alt = 2
mode_xml = 3
mode_sjson = 4
mode_replace = 5
mode_csv = 6
mode_map = 7

class modcode():
    def __init__(self,src,data,mode,key,**load):
        self.src = src
        self.data = data
        self.mode = mode
        self.key = key
        self.ep = load["ep"]

    def __repr__(self) -> str:
        return f"{self.data} {self.ep}"

def strup(string):
    return string[0].upper()+string[1:]

selffile = "".join(os.path.realpath(__file__).replace("\\","/").split(".")[:-1])+".py"
gamedir = os.path.join(os.path.realpath(gamerel), '').replace("\\","/")[:-1]
game = strup(gamedir.split("/")[-1])
game = game_aliases.get(game,game)

def in_directory(file,nobackup=True):
    ##if file.find(".pkg") == -1:
    ##    if not os.path.isfile(file):
    ##        return False
    file = os.path.realpath(file).replace("\\","/")
    if file == selffile:
        return False
    if nobackup:
        if os.path.commonprefix([file, gamedir+"/"+scope+"/"+bakdir]) == gamedir+"/"+scope+"/"+bakdir:
            return False
    return os.path.commonprefix([file, gamedir+"/"+scope]) == gamedir+"/"+scope

def valid_scan(file):
    if os.path.exists(file):
        if os.path.isdir(file):
            return True
    return False

def splitlines(body):
    glines = map(lambda s: s.strip().split("\""),body.split("\n"))
    lines = []
    li = -1
    mlcom = False
    def gp(group,lines,li,mlcom,even,lcom):
        if mlcom:
            tgroup = group.split(mlcom_end,1)
            if len(tgroup)==1: #still commented, carry on
                even = not even
                return (lines,li,mlcom,even,lcom)
            else: #comment ends, if a quote, even is disrupted
                even = False
                mlcom = False
                group = tgroup[1]
        if not mlcom:
            if even:
                lines[li]+="\""+group+"\""
            else:
                tgroup = group.split(comment,1)
                if len(tgroup) == 2:
                    lcom = True
                tline = tgroup[0].split(mlcom_start,1)
                tgroup = tline[0].split(linebreak)
                lines[li]+=tgroup[0] #uncommented line
                for g in tgroup[1:]: #new uncommented lines
                    lines.append(g)
                    li+=1
                if len(tline)>1: #comment begins
                    mlcom = True
                    lines,li,mlcom,even,lcom = gp(tline[1],lines,li,mlcom,even,lcom)
        return (lines,li,mlcom,even,lcom)
    for groups in glines:
        lcom = False
        even = False
        li += 1
        lines.append("")
        for group in groups:
            lines,li,mlcom,even,lcom = gp(group,lines,li,mlcom,even,lcom)
            if lcom:
                break
            even = not even
    return lines

def tokenise(line):
    groups = line.strip().split("\"")
    for i,group in enumerate(groups):
        if i%2:
            groups[i] = [group]
        else:
            groups[i] = group.replace(" ",delimiter).split(delimiter)
    tokens = []
    for group in groups:
        for x in group:
            if x != '':
                tokens.append(x)
    return tokens

## FILE/MOD LOADING

def startswith(tokens,keyword,n):
    return tokens[:len(keyword)] == keyword and len(tokens)>=len(keyword)+1

def loadcommand(reldir,tokens,to,n,mode,**load):
    for path in to:
        if in_directory(path):
            args = [tokens[i::n] for i in range(n)]
            for i in range(len(args[-1])):
                sources = [reldir+"/"+arg[i].replace("\"","").replace("\\","/") for arg in args]
                paths = []
                
                num = -1
                for source in sources:
                    LOGGER.info(source)
                    if valid_scan(source):
                        tpath = []
                        for file in os.scandir(source):
                            file = file.path.replace("\\","/")
                            if in_directory(file):
                                tpath.append(file)
                        paths.append(tpath)
                        if num > len(tpath) or num < 0:
                            num = len(tpath)
                    elif in_directory(source):
                        paths.append(source)
                if paths:
                    for j in range(abs(num)):
                        sources = [x[j] if isinstance(x,list) else x for x in paths]
                        codeargs = ('\n'.join(sources),tuple(sources),mode,path)
                        load["ep"] = load.get("ep",default_priority)
                        if load.get("reverse",False):
                            load["ep"] = -load["ep"]
                            codes[path].appendleft(modcode(*codeargs,**load))
                        else:
                            codes[path].append(modcode(*codeargs,**load))

def loadmodfile(filename,echo=True):
    if in_directory(filename):
        
        try:
            file = open(filename,'r',encoding='utf-8-sig')
        except IOError:
            return
        if echo:
            LOGGER.info(filename)

        reldir = "/".join(filename.split("/")[:-1])
        ep = 100
        to = default_to[game]
        
        with file:
            for line in splitlines(file.read()):
                tokens = tokenise(line) 
                if len(tokens)==0:
                    continue

                elif startswith(tokens,kwrd_to,0):
                    to = [s.replace("\\","/") for s in tokens[1:]]
                    if len(to) == 0:
                        to = default_to[game]
                elif startswith(tokens,kwrd_load,0):
                    n = len(kwrd_load)+len(kwrd_priority)
                    if tokens[len(kwrd_load):n] == kwrd_priority:
                        if len(tokens)>n:
                            try:
                                ep = int(tokens[n])
                            except ValueError:
                                pass
                        else:
                            ep = default_priority
                elif startswith(tokens,kwrd_priority,0):
                    n = len(kwrd_priority)
                    if tokens[:n] == kwrd_priority:
                        if len(tokens)>n:
                            try:
                                ep = int(tokens[n])
                            except ValueError:
                                pass
                        else:
                            ep = default_priority
                elif startswith(tokens,kwrd_include,1):
                    for s in tokens[1:]:
                        path = reldir+"/"+s.replace("\"","").replace("\\","/")
                        if valid_scan(path):
                            for file in os.scandir(path):
                                loadmodfile(file.path.replace("\\","/"),echo)
                        else:
                            loadmodfile(path,echo)
                elif startswith(tokens,kwrd_replace,1):
                    loadcommand(reldir,tokens[len(kwrd_replace):],to,1,mode_replace,ep=ep)
                elif startswith(tokens,kwrd_import,1):
                    loadcommand(reldir,tokens[len(kwrd_import):],to,1,mode_lua,ep=ep)
                elif startswith(tokens,kwrd_topimport,1):
                    loadcommand(reldir,tokens[len(kwrd_topimport):],to,1,mode_lua_alt,ep=ep,reverse=True)
                elif startswith(tokens,kwrd_xml,1):
                    loadcommand(reldir,tokens[len(kwrd_xml):],to,1,mode_xml,ep=ep)
                elif startswith(tokens,kwrd_csv,1):
                    loadcommand(reldir,tokens[len(kwrd_csv):],to,1,mode_csv,ep=ep)
                elif can_sjson and startswith(tokens,kwrd_sjson,1):
                    loadcommand(reldir,tokens[len(kwrd_sjson):],to,1,mode_sjson,ep=ep)
                elif can_mapper and startswith(tokens, kwrd_map,1):
                    loadcommand(reldir, tokens[len(kwrd_map):],to,1,mode_map,ep=ep)
                else:
                    raise Exception(f"Improper command from {filename}:\n\t{line}")

def isedited(base):
    if not (".lua" in base or ".xml" in base or ".sjson" in base or ".csv" in base):
        return True
    with open(base,'r',encoding='utf-8-sig') as basefile:
        for line in basefile:
              if modified+modified_modrep in line:
                  return True
    return False
         
def sortmods(mods):
    return sorted(mods,key=lambda x: x.ep)

def makeedit(base,mods,echo=True):
    Path("/".join(base.split("/")[:-1])).mkdir(parents=True, exist_ok=True)
    Path(bakdir+"/"+"/".join(base.split("/")[:-1])).mkdir(parents=True, exist_ok=True)
    if not os.path.exists(base):
        open(bakdir+"/"+base+baktype+".del","w").close()
    else:
        bakpath = bakdir+"/"+base+baktype
        if isedited(base) and in_directory(bakpath,False) and os.path.exists(bakpath):
            copyfile(bakpath,base)
        else:
            copyfile(base,bakpath)
    if echo:
        i=0
        LOGGER.info("\n"+base)
    try:
        cached_map_changes = {}
        for mod in mods:
            if mod.mode == mode_replace:
                copyfile(mod.data[0],base)
            elif mod.mode == mode_lua:
                addimport(base,mod.data[0])
            elif mod.mode == mode_lua_alt:
                addtopimport(base,mod.data[0])
            elif mod.mode == mode_xml:
                mergexml(base,mod.data[0])
            elif mod.mode == mode_sjson:
                mergesjson(base,mod.data[0])
            elif mod.mode == mode_map:
                cachemapchange(cached_map_changes, mod.data[0])
                # mergemap(base,)
            if echo:
                k = i+1
                for s in mod.src.split('\n'):
                    i+=1
                    LOGGER.info(" #"+str(i)+" +"*(k<i)+" "*((k>=i)+5-len(str(i)))+s)
        
        if len(cached_map_changes) > 0:
            changemap(base, cached_map_changes)
    except Exception as e:
        copyfile(bakdir+"/"+base+baktype,base)
        raise RuntimeError("Encountered uncaught exception while implementing mod changes") from e

    modifiedstr = ""
    if mods[0].mode in {mode_lua,mode_lua_alt}:
        modifiedstr = "\n"+modified_lua
    elif mods[0].mode == mode_xml:
        modifiedstr = "\n"+modified_xml
    elif mods[0].mode == mode_sjson:
        modifiedstr = "\n"+modified_sjson
    elif mods[0].mode == mode_csv:
         modifiedstr = "\n"+modified_csv
    elif mods[0].mode == mode_map:
        modifiedstr = modified_map
    with open(base,'a',encoding='utf-8') as basefile:
        basefile.write(modifiedstr.replace(modified,modified+modified_modrep+str(datetime.now())))

def cleanup(folder=bakdir,echo=True):
    if valid_scan(folder):
        empty = True
        for content in os.scandir(folder):
            if cleanup(content,echo):
                empty = False
        if empty:
            os.rmdir(folder)
            return False
        return True
    path = folder.path[len(bakdir)+1:]
    if path.find(".del") == len(path)-len(".del"):
        path = path[:-len(".del")]
        if echo:
            LOGGER.info(path)
        if os.path.exists(path):
            os.remove(path)
        if os.path.exists(folder.path):
            os.remove(folder.path)
        return False
    if os.path.isfile(path):
        if isedited(path):
            if echo:
                LOGGER.info(path)
            copyfile(folder.path,path)
            os.remove(folder.path)
            return False
        os.remove(folder.path)
        return False
    return True

def start():
    global codes
    codes = defaultdict(deque)

    LOGGER.info("Cleaning edits... (if there are issues validate/reinstall files)\n")
    Path(bakdir).mkdir(parents=True, exist_ok=True)
    cleanup()

    if clean_only:
        LOGGER.info( "Finished cleaning, skipping edits.\n" )
        return
    
    LOGGER.info("\nReading mod files...\n")
    Path(modsdir).mkdir(parents=True, exist_ok=True)
    for mod in os.scandir(modsdir):
        loadmodfile(mod.path.replace("\\","/")+"/"+modfile)

    LOGGER.info("\nModified files for "+game+" mods:")
    for base, mods in codes.items():
        LOGGER.debug(f"mods: {mods}")
        mods = sortmods(mods)
        LOGGER.debug(f"sorted: {mods}")
        makeedit(base,mods)

    bs = len(codes)
    ms = sum(map(len,codes.values()))

    LOGGER.info("\n"+str(bs)+" base file"+"s"*(bs!=1)+" import"+"s"*(bs==1)+" a total of "+str(ms)+" mod file"+"s"*(ms!=1)+".\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument( '--game', '-g', choices=[game for game in default_to], help="select game mode" )
    parser.add_argument( '--clean', '-c', action='store_true', help="clean only (uninstall mods)" )
    parser.add_argument('--verbose', '-v', action='store_true', help="verbose mode (default log level if not provided: info, '-v': debug)")
    parser.add_argument('--quiet', '-q', action='store_true', help="quiet mode (only log errors, overrides --verbose if present)")
    parser.add_argument('--no-input', action='store_false', default=True, dest='input', help="do not prompt for input when done (default: prompt for input)")
    args = parser.parse_args()
    # --game
    game = args.game or game
    # --clean
    if args.clean is not None:
        clean_only = args.clean
    # --quiet / --verbose
    if args.quiet:
        LOGGER.setLevel(logging.ERROR)
    elif args.verbose:
        LOGGER.setLevel(logging.DEBUG)
    try:
        start()
    except PermissionError as e:
        LOGGER.error(e)
        msg = """
[Recommended solution]
Right-click on Hades directory > Properties > Uncheck "Read-only" > Apply > re-run `modimporter`.

[If it does not work]
Re-run `modimporter` as administrator.
"""
        LOGGER.error(msg)
    except Exception as e:
        LOGGER.error("There was a critical error, now attempting to display the error")
        ##LOGGER.error("(Run this program again in a terminal that does not close or check the log file if this doesn't work)")
        logging.getLogger("MainExceptions").exception(e)
        ##raise RuntimeError("Encountered uncaught exception during program") from e
    if args.input:
        input("Press ENTER/RETURN to end program...")
