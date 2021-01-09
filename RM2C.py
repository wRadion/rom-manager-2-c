import struct
import GeoWrite as GW
import F3D
import ColParse
import sys
import os
from pathlib import Path
from capstone import *
import shutil
from bitstring import *
from RM2CData import *
import BinPNG
import groups as GD

class Script():
	def __init__(self,level):
		self.mapF = open('sm64.us.map','r')
		self.map=self.mapF.readlines()
		self.banks=[None for a in range(32)]
		self.asm=[[0x80400000,0x1200000,0x1220000]]
		self.models=[None for a in range(256)]
		self.Currlevel=level
		self.levels={}
		self.levels[self.Currlevel]=[None for a in range(8)]
		#stack is simply a stack of ptrs
		#base is the prev pos
		#top is the current pos
		self.Base=None
		self.Stack=[]
		self.Top=-1
		self.CurrArea=None
		self.header=[]
	def B2P(self,B):
		Bank=B>>24
		offset=B&0xFFFFFF
		seg = self.banks[Bank]
		if not seg:
			# print(hex(B),hex(Bank),self.banks[Bank-2:Bank+3])
			raise ''
		return seg[0]+offset
	def L4B(self,T):
		x=0
		for i,b in enumerate(T):
			x+=b<<(8*(3-i))
		return x
	def GetArea(self):
		try:
			return self.levels[self.Currlevel][self.CurrArea]
		except:
			return None
	def GetNumAreas(self,level):
		count=[]
		for i,area in enumerate(self.levels[level]):
			if area:
				count.append(i)
		return count
	def GetLabel(self,addr):
		#behavior is in bank 0 and won't be in map ever
		if addr[0:2]=='00':
			print(addr + 'is in bank 0 cannot be found')
			return '0x'+addr
		for l in self.map:
			if addr in l:
				q = l.rfind(" ")
				return l[q:-1]
		return "0x"+addr
	def GetAddr(self,label):
		for l in self.map:
			if label in l:
				return "0x"+l.split("0x")[1][8:16]
		return None
	def RME(self,num,rom):
		if self.editor:
			return
		start=self.B2P(0x19005f00)
		start=TcH(rom[start+num*16:start+num*16+4])
		end=TcH(rom[start+4+num*16:start+num*16+8])
		self.banks[0x0e]=[start,end]
	def MakeDec(self,name):
		self.header.append(name)
	def Seg2(self,rom):
		UPH = (lambda x,y: struct.unpack(">H",x[y:y+2])[0])
		start=UPH(rom,0x3ac2)<<16
		start+=UPH(rom,0x3acE)
		end=UPH(rom,0x3ac6)<<16
		end+=UPH(rom,0x3acA)
		#mio0 for seg2 just happens to expand start by 0x3156 idk how it really works
		self.banks[2]=[start+0x3156,end+0x3156]

class Area():
		def __init__(self):
			pass

#tuple convert to hex
def TcH(bytes):
	a = struct.pack(">%dB"%len(bytes),*bytes)
	if len(bytes)==4:
		return struct.unpack(">L",a)[0]
	if len(bytes)==2:
		return struct.unpack(">H",a)[0]
	if len(bytes)==1:
		return struct.unpack(">B",a)[0]

def U2S(half):
	return struct.unpack(">h",struct.pack(">H",half))[0]

def LoadRawJumpPush(rom,cmd,start,script):
	arg=cmd[2]
	bank=arg[0:2]
	begin = arg[2:6]
	end = arg[6:10]
	jump = arg[10:14]
	script.banks[TcH(bank)]=[TcH(begin),TcH(end)]
	script.Stack.append(start)
	script.Top+=1
	script.Stack.append(script.Base)
	script.Top+=1
	script.Base=script.Top
	return script.B2P(TcH(jump))

def LoadRawJump(rom,cmd,start,script):
	arg=cmd[2]
	bank=arg[0:2]
	begin = arg[2:6]
	end = arg[6:10]
	jump = arg[10:14]
	script.banks[TcH(bank)]=[TcH(begin),TcH(end)]
	script.Top=script.Base
	return script.B2P(TcH(jump))

def Exit(rom,cmd,start,script):
	script.Top=script.Base
	script.Base=script.Stack[script.Top]
	script.Stack.pop()
	script.Top-=1
	start=script.Stack[script.Top]
	script.Stack.pop()
	script.Top-=1
	return start
	
def JumpRaw(rom,cmd,start,script):
	arg=cmd[2]
	return script.B2P(TcH(arg[2:6]))
	
def JumpPush(rom,cmd,start,script):
	script.Top+=1
	script.Stack.append(start)
	arg=cmd[2]
	return script.B2P(TcH(arg[2:6]))
	
def Pop(rom,cmd,start,script):
	start=script.Stack[script.Top]
	script.Top-=1
	script.Stack.pop()
	return start
	
def CondPop(rom,cmd,start,script):
	#this is where the script loops
	#Ill assume no custom shit is done
	#meaning this will always signal end of level
	return None

def CondJump(rom,cmd,start,script):
	arg=cmd[2]
	level=arg[2:6]
	jump=arg[6:10]
	if script.Currlevel==TcH(level):
		return script.B2P(TcH(jump))
	else:
		return start
	
def SetLevel(rom,cmd,start,script):
	#gonna ignore this and take user input instead
	#script.Currlevel=TcH(cmd[2])
	# if not script.levels.get("Currlevel"):
		# script.levels[script.Currlevel]=[None for a in range(8)]
	return start
	
def LoadAsm(rom,cmd,start,script):
	arg=cmd[2]
	ram=arg[2:6]
	begin=arg[6:10]
	end=arg[10:14]
	Q=[TcH(ram),TcH(begin),TcH(end)]
	if Q not in script.asm:
		script.asm.append(Q)
	return start

def LoadData(rom,cmd,start,script):
	arg=cmd[2]
	bank=arg[1:2]
	begin = arg[2:6]
	end = arg[6:10]
	script.banks[TcH(bank)]=[TcH(begin),TcH(end)]
	return start

def LoadMio0(rom,cmd,start,script):
	pass
	
def LoadMio0Tex(rom,cmd,start,script):
	return LoadData(rom,cmd,start,script)

def StartArea(rom,cmd,start,script):
	#ignore stuff in bank 0x14 because thats star select/file select and messes up export
	arg=cmd[2]
	if TcH(arg[2:3])==0x14:
		return start
	area=arg[0]+script.Aoffset
	script.CurrArea=area
	q=Area()
	q.geo=TcH(arg[2:6])
	q.objects=[]
	q.warps=[]
	q.rom=rom
	script.levels[script.Currlevel][script.CurrArea]=q
	return start
	
def EndArea(rom,cmd,start,script):
	script.CurrArea=None
	return start
	
def LoadPolyF3d(rom,cmd,start,script):
	arg=cmd[2]
	id=arg[1:2]
	layer=TcH(arg[0:1])>>4
	f3d=TcH(arg[2:6])
	script.models[TcH(id)]=(f3d,'f3d',layer,script.B2P(f3d))
	return start
	
def LoadPolyGeo(rom,cmd,start,script):
	arg=cmd[2]
	id=arg[1:2]
	geo=TcH(arg[2:6])
	script.models[TcH(id)]=(geo,'geo',None,script.B2P(geo))
	return start
	
def PlaceObject(rom,cmd,start,script):
	arg=cmd[2]
	A=script.GetArea()
	if not A:
		return start
	mask=arg[0]
	#remove disabled objects
	if mask==0:
		return start
	id=arg[1]
	#efficiency
	x=U2S(TcH(arg[2:4]))
	y=U2S(TcH(arg[4:6]))
	z=U2S(TcH(arg[6:8]))
	rx=U2S(TcH(arg[8:10]))
	ry=U2S(TcH(arg[10:12]))
	rz=U2S(TcH(arg[12:14]))
	bparam=hex(TcH(arg[14:18]))
	bhv=script.GetLabel("{:08x}".format(TcH(arg[18:22])))
	#print(bhv)
	PO=(id,x,y,z,rx,ry,rz,bparam,bhv,mask)
	A.objects.append(PO)
	return start
	
def PlaceMario(rom,cmd,start,script):
	#do nothing
	return start

def ConnectWarp(rom,cmd,start,script):
	A=script.GetArea()
	if not A:
		return start
	arg=cmd[2]
	W=(arg[0],arg[1],arg[2]+script.Aoffset,arg[3],arg[4])
	A.warps.append(W)
	return start
	
def PaintingWarp(rom,cmd,start,script):
	return start
	
def InstantWarp(rom,cmd,start,script):
	return start
	
def SetMarioDefault(rom,cmd,start,script):
	arg=cmd[2]
	script.mStart = [arg[0],U2S(TcH(arg[2:4])),U2S(TcH(arg[4:6])),U2S(TcH(arg[6:8])),U2S(TcH(arg[8:10]))]
	return start
	
def LoadCol(rom,cmd,start,script):
	arg=cmd[2]
	col=TcH(arg[2:6])
	A=script.GetArea()
	if not A:
		return start
	A.col=col
	return start
	
def LoadRoom(rom,cmd,start,script):
	return start

def SetDialog(rom,cmd,start,script):
	return start

def SetMusic(rom,cmd,start,script):
	A=script.GetArea()
	if A:
		arg=cmd[2]
		A.music=TcH(arg[3:4])
	return start

def SetMusic2(rom,cmd,start,script):
	A=script.GetArea()
	if A:
		arg=cmd[2]
		A.music=TcH(arg[1:2])
	return start

def SetTerrain(rom,cmd,start,script):
	A=script.GetArea()
	if A:
		arg=cmd[2]
		A.terrain=TcH(arg[1:2])
	return start

def ULC(rom,start):
	cmd = struct.unpack(">B",rom[start:start+1])[0]
	len = struct.unpack(">B",rom[start+1:start+2])[0]
	q=len-2
	args = struct.unpack(">%dB"%q,rom[start+2:start+len])
	return [cmd,len,args]

#iterates through script until a cmd is found that
#requires new action, then returns that cmd
def PLC(rom,start):
	(cmd,len,args) = ULC(rom,start)
	start+=len
	if cmd in jumps:
		return (cmd,len,args,start)
	return PLC(rom,start)

def WriteModel(rom,dls,s,name,Hname,id,tdir):
	x=0
	ModelData=[]
	while(x<len(dls)):
		#check for bad ptr
		st=dls[x][0]
		first=TcH(rom[st:st+4])
		c=rom[st]
		if first==0x01010101 or not F3D.DecodeFmt.get(c):
			return
		(dl,verts,textures,amb,diff,jumps,ranges)=F3D.DecodeDL(rom,dls[x],s,id)
		ModelData.append([dls[x],dl,verts,textures,amb,diff,ranges])
		for jump in jumps:
			if jump not in dls:
				dls.append(jump)
		x+=1
	refs = F3D.ModelWrite(rom,ModelData,name,id,tdir)
	modelH = name/'custom.model.inc.h'
	mh = open(modelH,'w')
	headgaurd="%s_HEADER_H"%(Hname)
	mh.write('#ifndef %s\n#define %s\n#include "types.h"\n'%(headgaurd,headgaurd))
	for r in refs:
		mh.write('extern '+r+';\n')
	mh.write("#endif")
	mh.close()
	return dls

def ClosestIntinDict(num,dict):
	min=0xFFFFFFFFFFFFFF
	res = None
	for k,v in dict.items():
		if abs(k-num)<min:
			min=abs(k-num)
			res = v
	return res

def InsertBankLoads(s,f):
	banks = [s.banks[10],s.banks[15],s.banks[12],s.banks[13]]
	for i,b in enumerate(banks):
		if not i:
			if s.editor:
				d=skyboxesEditor
			else:
				d=skyboxesRM
		else:
			d=Groups
		if b:
			banks[i]=ClosestIntinDict(b[0],d)
			if not i:
				#custom skybox
				if b[0]>0x1220000:
					name = '_%s_skybox_mio0'%('SkyboxCustom%d'%b[0])
					load = "LOAD_MIO0(0xA,"+banks[i]+"SegmentRomStart,"+banks[i]+"SegmentRomEnd),\n"
				else:
					load = "LOAD_MIO0(0xA,"+banks[i]+"SegmentRomStart,"+banks[i]+"SegmentRomEnd),\n"
			else:
				load = "LOAD_MIO0(%d,"%banks[i][1]+banks[i][0]+"_mio0SegmentRomStart,"+banks[i][0]+"_mio0SegmentRomEnd),\n"
				load += "LOAD_RAW(%d,"%banks[i][2]+banks[i][0]+"_geoSegmentRomStart,"+banks[i][0]+"_geoSegmentRomEnd),\n"
			f.write(load)
	return banks

def DetLevelSpecBank(s,f):
	level = None
	if s.banks[7]:
		#RM custom bank 7 check
		if s.banks[7][0]>0x1220000:
			return level
		level =ClosestIntinDict(s.banks[7][0],LevelSpecificBanks)
	return level

def LoadUnspecifiedModels(s,file,level):
	Grouplines = Group_Models.split("\n")
	for i,model in enumerate(s.models):
		if model:
			#Bank 0x14 is for menus, I will ignore it
			Seg = (model[0]>>24)
			if Seg==0x14:
				continue
			#Model Loads need to use groups because seg addresses are repeated so you can get the wrong ones
			#if you just use the map which has no distinction on which bank is loaded.
			addr = "{:08x}".format(model[0])
			if Seg==0x12:
				lab = GD.__dict__[level].get((i,'0x'+addr))[1]
			#actor groups, unlikely to exist outside existing group loads
			if Seg==0xD or Seg==0xC:
				group = ClosestIntinDict(s.banks[Seg][0],Groups)[0][1:]
				lab = GD.__dict__[group].get((i,'0x'+addr))[1]
			#group0, common0, common1 banks that have unique geo layouts
			else:
				lab = s.GetLabel(addr)
			if '0x' in lab or not lab:
				comment = "// "
			else:
				comment = ""
			if not (any([lab in l for l in Grouplines])):
				if model[1]=='geo':
					file.write(comment+"LOAD_MODEL_FROM_GEO(%d,%s),\n"%(i,lab))
				else:
					#Its just a guess but I think 4 will lead to the least issues
					file.write(comment+"LOAD_MODEL_FROM_DL(%d,%s,4),\n"%(i,lab))

def WriteLevelScript(name,Lnum,s,level,Anum,envfx):
	f = open(name,'w')
	f.write(scriptHeader)
	f.write('#include "levels/%s/header.h"\nextern u8 _%s_segment_ESegmentRomStart[]; \nextern u8 _%s_segment_ESegmentRomEnd[];\n'%(Lnum,Lnum,Lnum))
	#This is the ideal to match hacks, but currently the way the linker is
	#setup, level object data is in the same bank as level mesh so this cannot be done.
	LoadLevel = DetLevelSpecBank(s,f)
	if LoadLevel and LoadLevel!=Lnum:
		f.write('#include "levels/%s/header.h"\n'%LoadLevel)
	f.write('const LevelScript level_%s_custom_entry[] = {\n'%Lnum)
	s.MakeDec('const LevelScript level_%s_custom_entry[]'%Lnum)
	#entry stuff
	f.write("INIT_LEVEL(),\n")
	if LoadLevel:
		f.write("LOAD_MIO0(0x07, _"+LoadLevel+"_segment_7SegmentRomStart, _"+LoadLevel+"_segment_7SegmentRomEnd),\n")
		f.write("LOAD_RAW(0x1A, _"+LoadLevel+"SegmentRomStart, _"+LoadLevel+"SegmentRomEnd),\n")
	f.write("LOAD_RAW(0x0E, _"+Lnum+"_segment_ESegmentRomStart, _"+Lnum+"_segment_ESegmentRomEnd),\n")
	if envfx:
		f.write("LOAD_MIO0(        /*seg*/ 0x0B, _effect_mio0SegmentRomStart, _effect_mio0SegmentRomEnd),\n")
	#add in loaded banks
	banks = InsertBankLoads(s,f)
	f.write("ALLOC_LEVEL_POOL(),\nMARIO(/*model*/ MODEL_MARIO, /*behParam*/ 0x00000001, /*beh*/ bhvMario),\n")
	if LoadLevel:
		f.write(LevelSpecificModels[LoadLevel])
	#Load models that the level uses that are outside groups/level
	LoadUnspecifiedModels(s,f,LoadLevel)
	#add in jumps based on banks returned
	for b in banks:
		if type(b)==list:
			f.write("JUMP_LINK("+b[3]+"),\n")
	#a bearable amount of cringe
	for a in Anum:
		id = Lnum+"_"+str(a)+"_"
		f.write('JUMP_LINK(local_area_%s),\n'%id)
	#end script
	f.write("FREE_LEVEL_POOL(),\n")
	f.write("MARIO_POS({},{},{},{},{}),\n".format(*s.mStart))
	f.write("CALL(/*arg*/ 0, /*func*/ lvl_init_or_update),\nCALL_LOOP(/*arg*/ 1, /*func*/ lvl_init_or_update),\nCLEAR_LEVEL(),\nSLEEP_BEFORE_EXIT(/*frames*/ 1),\nEXIT(),\n};\n")
	for a in Anum:
		id = Lnum+"_"+str(a)+"_"
		area=level[a]
		WriteArea(f,s,area,a,id)

def WriteArea(f,s,area,Anum,id):
	#begin area
	ascript = "const LevelScript local_area_%s[]"%id
	f.write(ascript+' = {\n')
	s.MakeDec(ascript)
	Gptr='Geo_'+id+hex(area.geo)
	f.write("AREA(%d,%s),\n"%(Anum,Gptr))
	f.write("TERRAIN(%s),\n"%("col_"+id+hex(area.col)))
	f.write("SET_BACKGROUND_MUSIC(0,%d),\n"%area.music)
	f.write("TERRAIN_TYPE(%d),\n"%(area.terrain))
	f.write("JUMP_LINK(local_objects_%s),\nJUMP_LINK(local_warps_%s),\n"%(id,id))
	f.write("END_AREA(),\nRETURN()\n};\n")
	asobj = 'const LevelScript local_objects_%s[]'%id
	f.write(asobj+' = {\n')
	s.MakeDec(asobj)
	#write objects
	for o in area.objects:
		f.write("OBJECT_WITH_ACTS({},{},{},{},{},{},{},{},{},{}),\n".format(*o))
	f.write("RETURN()\n};\n")
	aswarps = 'const LevelScript local_warps_%s[]'%id
	f.write(aswarps+' = {\n')
	s.MakeDec(aswarps)
	#write warps
	for w in area.warps:
		f.write("WARP_NODE({},{},{},{},{}),\n".format(*w))
	f.write("RETURN()\n};\n")

def GrabOGDatH(q,rootdir,name):
	dir = rootdir/'originals'/name
	head = open(dir/'header.h','r')
	head = head.readlines()
	for l in head:
		if not l.startswith('extern'):
			continue
		q.write(l)
	return q

def GrabOGDatld(L,rootdir,name):
	dir = rootdir/'originals'/name
	ld = open(dir/'leveldata.c','r')
	ld = ld.readlines()
	grabbed = []
	for l in ld:
		if not l.startswith('#include "levels/%s/'%name):
			continue
		#mem bloat but makes up for mov tex being dumb
		# if ('/areas/' in l and '/model.inc.c' in l):
			# continue
		#for the specific case of levels without subfolders
		q = l.split('/')
		if len(q)>4:
			if ('areas' in q[2] and 'model.inc.c' in q[4]):
				continue
		#I want to include static objects in collision
		# if ('/areas/' in l and '/collision.inc.c' in l):
			# continue
		L.write(l)
		grabbed.append(l)
	return [L,grabbed]

def WriteVanillaLevel(rom,s,num,areas,rootdir,m64dir,AllWaterBoxes,Onlys,romname,m64s,seqNums,MusicExtend):
	#create level directory
	WaterOnly = Onlys[0]
	ObjectOnly = Onlys[1]
	MusicOnly = Onlys[2]
	OnlySkip = any(Onlys)
	name=Num2Name[num]
	level=Path(sys.path[0])/'levels'/("%s"%name)
	original = rootdir/'originals'/("%s"%name)
	shutil.copytree(original,level)
	#open original script
	script = level / 'script.c'
	scriptO = open(script,'r')
	Slines = scriptO.readlines()
	scriptO.close()
	script = open(script,'w')
	#go until an area is found
	x=0 #line pos
	restrict = ['OBJECT','WARP_NODE','JUMP_LINK']
	CheckRestrict = (lambda x: any([r in x for r in restrict]))
	for a in areas:
		j=0
		area=s.levels[num][a]
		while(True):
			if 'AREA(' in Slines[x]:
				x+=1
				break
			x+=1
		#remove other objects/warps
		while(True):
			if CheckRestrict(Slines[j+x]):
				Slines.pop(j+x)
				continue
			elif 'END_AREA()' in Slines[j+x]:
				j+=1
				break
			else:
				j+=1
		for o in area.objects:
			Slines.insert(x,"OBJECT_WITH_ACTS({},{},{},{},{},{},{},{},{},{}),\n".format(*o))
		for w in area.warps:
			Slines.insert(x,"WARP_NODE({},{},{},{},{}),\n".format(*w))
		x=j+x
		#area dir
		Arom = area.rom
		if area.music and not (ObjectOnly or WaterOnly):
			[m64,seqNum] = RipSequence(Arom,area.music,m64dir,num,a,romname,MusicExtend)
			if m64 not in m64s:
				m64s.append(m64)
				seqNums.append(seqNum)
		#write objects and warps for each area
	[script.write(l) for l in Slines]
	return [AllWaterBoxes,m64s,seqNums]

def WriteLevel(rom,s,num,areas,rootdir,m64dir,AllWaterBoxes,Onlys,romname,m64s,seqNums,MusicExtend):
	#create level directory
	WaterOnly = Onlys[0]
	ObjectOnly = Onlys[1]
	MusicOnly = Onlys[2]
	OnlySkip = any(Onlys)
	name=Num2Name[num]
	level=Path(sys.path[0])/'levels'/("%s"%name)
	original = rootdir/'originals'/("%s"%name)
	shutil.copytree(original,level)
	Areasdir = level/"areas"
	Areasdir.mkdir(exist_ok=True)
	#create area directory for each area
	envfx = 0
	for a in areas:
		#area dir
		adir = Areasdir/("%d"%a)
		adir.mkdir(exist_ok=True)
		area=s.levels[num][a]
		Arom = area.rom
		if area.music and not (ObjectOnly or WaterOnly):
			[m64,seqNum] = RipSequence(Arom,area.music,m64dir,num,a,romname,MusicExtend)
			if m64 not in m64s:
				m64s.append(m64)
				seqNums.append(seqNum)
		#get real bank 0x0e location
		s.RME(a,Arom)
		id = name+"_"+str(a)+"_"
		(geo,dls,WB,vfx)=GW.GeoParse(Arom,s.B2P(area.geo),s,area.geo,id)
		#deal with some areas having it vs others not
		if vfx:
			envfx = 1
		if not OnlySkip:
			GW.GeoWrite(geo,adir/"custom.geo.inc.c",id)
			for g in geo:
				s.MakeDec("const GeoLayout Geo_%s[]"%(id+hex(g[1])))
		if not OnlySkip:
			dls = WriteModel(Arom,dls,s,adir,"%s_%d"%(name.upper(),a),id,level)
			for d in dls:
				s.MakeDec("const Gfx DL_%s[]"%(id+hex(d[1])))
		#write collision file
		if not OnlySkip:
			ColParse.ColWrite(adir/"custom.collision.inc.c",s,Arom,area.col,id)
		s.MakeDec('const Collision col_%s[]'%(id+hex(area.col)))
		#write mov tex file
		if not (ObjectOnly or MusicOnly):
			#WB = [types][array of type][box data]
			MovTex = adir / "movtextNew.inc.c"
			MovTex = open(MovTex,'w')
			Wrefs = []
			for k,Boxes in enumerate(WB):
				wref = []
				for j,box in enumerate(Boxes):
					#Now a box is an array of all the data
					#Movtex is just an s16 array, it uses macros but
					#they don't matter
					dat = repr(box).replace("[","{").replace("]","}")
					dat = "static Movtex %sMovtex_%d_%d[] = "%(id,j,k) + dat+";\n\n"
					MovTex.write(dat)
					wref.append("%sMovtex_%d_%d"%(id,k,j))
				Wrefs.append(wref)
			for j,Type in enumerate(Wrefs):
				MovTex.write("const struct MovtexQuadCollection %sMovtex_%d[] = {\n"%(id,j))
				for k,ref in enumerate(Type):
					MovTex.write("{%d,%s},\n"%(k,ref))
				MovTex.write("{-1, NULL},\n};")
				s.MakeDec("struct MovtexQuadCollection %sMovtex_%d[]"%(id,j))
				AllWaterBoxes.append(["%sMovtex_%d"%(id,j),num,a,j])
		print('finished area '+str(a)+ ' in level '+name)
	#now write level script
	if not (WaterOnly or MusicOnly):
		WriteLevelScript(level/"custom.script.c",name,s,s.levels[num],areas,envfx)
	s.MakeDec("const LevelScript level_%s_entry[]"%name)
	if not OnlySkip:
		#finally write header
		H=level/"header.h"
		q = open(H,'w')
		headgaurd="%s_HEADER_H"%(name.upper())
		q.write('#ifndef %s\n#define %s\n#include "types.h"\n#include "game/moving_texture.h"\n'%(headgaurd,headgaurd))
		for h in s.header:
			q.write('extern '+h+';\n')
		#now include externs from stuff in original level
		q = GrabOGDatH(q,rootdir,name)
		q.write("#endif")
		q.close()
		#append to geo.c, maybe the original works good always??
		G = level/"custom.geo.c"
		g = open(G,'w')
		g.write(geocHeader)
		g.write('#include "levels/%s/header.h"\n'%name)
		for i,a in enumerate(areas):
			geo = '#include "levels/%s/areas/%d/custom.geo.inc.c"\n'%(name,(i+1))
			g.write(geo) #add in some support for level specific objects somehow
		g.close
		#write leveldata.c
		LD = level/"custom.leveldata.c"
		ld = open(LD,'w')
		ld.write(ldHeader)
		Ftypes = ['custom.model.inc.c"\n','custom.collision.inc.c"\n']
		for i,a in enumerate(areas):
			ld.write('#include "levels/%s/areas/%d/movtextNew.inc.c"\n'%(name,(i+1)))
			start = '#include "levels/%s/areas/%d/'%(name,(i+1))
			for Ft in Ftypes:
					ld.write(start+Ft)
		ld.write('#include "levels/%s/textureNew.inc.c"\n'%(name))
		ld.close
	return [AllWaterBoxes,m64s,seqNums]

#Finds out what model is based on seg addr and loaded banks
def ProcessModel(rom,editor,s,modelID,model):
	Seg=model[0]>>24
	folder=None
	bank = s.banks[Seg]
	#A custom bank will be one that is loaded well after
	#all other banks are. This is not guaranteed, but nominal bhv
	if bank[0]>0x1220000:
		return ('Custom_%d'%bank[0],Seg,label)
	#These are in Seg C, D, F, 16, 17
	if Seg!=7 and Seg!=0x12:
		group = ClosestIntinDict(bank[0],Groups)[0][1:]
		label = GD.__dict__[group].get((modelID,"0x{:08x}".format(model[0])))
		if label:
			folder = label[2]
			label=label[1]
	#These are all in bank 7 with geo layouts in bank 12
	else:
		group = ClosestIntinDict(bank[0],LevelSpecificBanks)
		label = GD.__dict__[group].get((modelID,"0x{:08x}".format(model[0])))
		if label:
			folder = label[2]
			label=label[1]
	return (group,Seg,label,folder)

#process all the script class objects from all exported levels to find specific data
def ProcessScripts(rom,editor,Scripts):
	#key=banknum, value = list of start/end locations
	Banks = {}
	#key=group name, values = [seg num,label,type,rom addr,ID,folder]
	Models = {}
	for s in Scripts:
		#banks
		for k,B in enumerate(s.banks):
			if B:
				dupe = Banks.get(k)
				#check for duplicate which should be the case often
				if dupe and B not in dupe:
					Banks[k].append(B)
				else:
					Banks[k] = [B]
		#models
		for k,M in enumerate(s.models):
			if M:
				[group,seg,l,f] = ProcessModel(rom,editor,s,k,M)
				dupe = Models.get(group)
				val = [seg,l,M[1],M[3],k,f]
				#check for duplicate which should be the case often
				if dupe and val not in dupe:
					Models[group].append(val)
				else:
					Models[group] = [val]
	return [Banks,Models]

#dictionary of actions to take based on script cmds
jumps = {
    0:LoadRawJumpPush,
    1:LoadRawJump,
    2:Exit,
    5:JumpRaw,
    6:JumpPush,
    7:Pop,
    11:CondPop,
    12:CondJump,
    0x13:SetLevel,
    0x16:LoadAsm,
    0x17:LoadData,
    0x18:LoadMio0,
    0x1a:LoadMio0Tex,
    0x1f:StartArea,
    0x20:EndArea,
    0x21:LoadPolyF3d,
    0x22:LoadPolyGeo,
    0x24:PlaceObject,
    0x25:PlaceMario,
    0x26:ConnectWarp,
    0x27:PaintingWarp,
    0x28:InstantWarp,
    0x2b:SetMarioDefault,
    0x2e:LoadCol,
    0x2f:LoadRoom,
    0x30:SetDialog,
    0x31:SetTerrain,
    0x36:SetMusic,
    0x37:SetMusic2
}

def RipSequence(rom,seqNum,m64Dir,Lnum,Anum,romname,MusicExtend):
	#audio_dma_copy_immediate loads gSeqFileHeader in audio_init at 0x80319768
	#the line of asm is at 0xD4768 which sets the arg to this
	UPW = (lambda x,y: struct.unpack(">L",x[y:y+4])[0])
	gSeqFileHeader=(UPW(rom,0xD4768)&0xFFFF)<<16 #this is LUI asm cmd
	gSeqFileHeader+=(UPW(rom,0xD4770)&0xFFFF) #this is an addiu asm cmd
	#format is tbl,m64s[]
	#tbl format is [len,offset][]
	gSeqFileOffset = gSeqFileHeader+seqNum*8+4
	len=UPW(rom,gSeqFileOffset+4)
	offset=UPW(rom,gSeqFileOffset)
	m64 = rom[gSeqFileHeader+offset:gSeqFileHeader+offset+len]
	m64File = m64Dir/("{1:02X}_Seq_{0}_custom.m64".format(romname,seqNum+MusicExtend))
	m64Name = "{1:02X}_Seq_{0}_custom".format(romname,seqNum+MusicExtend)
	f = open(m64File,'wb')
	f.write(m64)
	f.close()
	return [m64Name,seqNum+MusicExtend]

def CreateSeqJSON(romname,m64s,rootdir,MusicExtend):
	m64Dir = rootdir/"sound"
	m64Dir.mkdir(exist_ok=True)
	originals = rootdir/"originals"/"sequences.json"
	m64s.sort(key=(lambda x: x[1]))
	origJSON = open(originals,'r')
	origJSON = origJSON.readlines()
	#This is the location of the Bank to Sequence table.
	seqMagic = 0x7f0000
	#format is u8 len banks (always 1), u8 bank. Maintain the comment/bank 0 data of the original sequences.json
	UPB = (lambda x,y: struct.unpack(">B",x[y:y+1])[0])
	UPH = (lambda x,y: struct.unpack(">h",x[y:y+2])[0])
	seqJSON = m64Dir/"sequences.json"
	seqJSON = open(seqJSON,'w')
	last = 0
	for m64 in m64s:
		bank = UPH(rom,seqMagic+(m64[1]-MusicExtend)*2)
		bank = UPB(rom,seqMagic+bank+1)
		if MusicExtend:
			seqJSON.write("\t\"{}\": [\"{}\"],\n".format(m64[0],SoundBanks[bank]))
			continue
		#fill in missing sequences
		for i in range(last,m64[1]+2,1):
			if i>36:
				break
			if i==36:
				seqJSON.write(origJSON[i][:-1]+',\n')
				break
			seqJSON.write(origJSON[i])
		seqJSON.write("\t\"{}\": [\"{}\"],\n".format(m64[0],SoundBanks[bank]))
		if m64[1]<0x23:
			og = origJSON[m64[1]]
			og = og.split(":")[0] + ": null,\n"
			seqJSON.write(og)
		last = m64[1]+2
	seqJSON.write("}")

def AppendAreas(entry,script,Append):
	for rom,offset,editor in Append:
		script.Aoffset = offset
		script.editor = editor
		Arom=open(rom,'rb')
		Arom = Arom.read()
		#get all level data from script
		while(True):
			#parse script until reaching special
			q=PLC(Arom,entry)
			#execute special cmd
			entry = jumps[q[0]](Arom,q,q[3],script)
			#check for end, then loop
			if not entry:
				break
	return script

def ExportLevel(rom,level,editor,Append,AllWaterBoxes,Onlys,romname,m64s,seqNums,MusicExtend,lvldefs):
	#choose level
	s = Script(level)
	s.Seg2(rom)
	entry = 0x108A10
	s = AppendAreas(entry,s,Append)
	s.Aoffset = 0
	s.editor = editor
	rootdir = Path(sys.path[0])
	m64dir = rootdir/'sound'/"sequences"/"us"
	os.makedirs(m64dir,exist_ok=True)
	#get all level data from script
	while(True):
		#parse script until reaching special
		q=PLC(rom,entry)
		#execute special cmd
		entry = jumps[q[0]](rom,q,q[3],s)
		#check for end, then loop
		if not entry:
			break
	#this tool isn't for exporting vanilla levels
	#so I export only objects for these levels
	if not s.banks[0x19]:
		WriteVanillaLevel(rom,s,level,s.GetNumAreas(level),rootdir,m64dir,AllWaterBoxes,[Onlys[0],1,Onlys[0]],romname,m64s,seqNums,MusicExtend)
		return s
	LevelName = {**Num2Name}
	lvldefs.write("DEFINE_LEVEL(%s,%s)\n"%(Num2Name[level],"LEVEL_"+Num2LevelName.get(level,'castle').upper()))
	#now do level
	WriteLevel(rom,s,level,s.GetNumAreas(level),rootdir,m64dir,AllWaterBoxes,Onlys,romname,m64s,seqNums,MusicExtend)
	return s

def ExportActors(actors,rom,Banks,Models,editor):
	for group,M in Models.items():
	#key=group name, values = [seg num,label,type,rom addr,ID,folder]
		print(group)
		for m in M:
			print(m)

def FindCustomSkyboxse(rom,Banks,SB):
	custom = {}
	for j,B in enumerate(Banks[0xA]):
		if B[0]>0x1220000:
			custom[B[0]] = '_SkyboxCustom%d'%B[0]
	#make some skybox rules for the linker so it can find these
	f = open(SB / 'Skybox_Rules.ld','w')
	for v in custom.values():
		f.write('   MIO0_SEG({}, 0x0A000000)\n'.format(v[1:]))
	return custom

def ExportTextures(rom,editor,rootdir,Banks):
	s=Script(9)
	s.Seg2(rom)
	Textures = rootdir/"textures"
	Textures.mkdir(exist_ok=True)
	#There are several different banks of textures, all are in bank 0xA or 0xB or 0x2
	#Editor and RM have different bank load locations, this is because editor didn't follow alignment
	#Seg2 func accounts for this by detecting the asm load, other banks will have to use different dicts
	#Skyboxes are first. Each skybox has its own bank. This alg will export each skybox tile, then merge
	#them into one skybox and delete them all. Its pretty slow.
	SB = Textures/'skyboxes'
	SB.mkdir(exist_ok=True)
	if editor:
		skyboxes=skyboxesEditor
	else:
		skyboxes = skyboxesRM
	#Check for custom skyboxes using Banks
	skyboxes = {**FindCustomSkyboxse(rom,Banks,SB),**skyboxes}
	for k,v in skyboxes.items():
		imgs = []
		name = v.split('_')[1]
		for i in range(0x40):
			namet = v.split('_')[1]+str(i)
			box = BinPNG.MakeImage(str(SB / namet))
			bin = rom[k+i*0x800:k+0x800+i*0x800]
			BinPNG.RGBA16(32,32,bin,box)
			imgs.append(box)
		FullBox = BinPNG.InitSkybox(str(SB / name))
		for j,tile in enumerate(imgs):
			x=(j*31)%248
			y=int((j*31)/248)*31
			tilepath = Path(tile.name)
			tile.close()
			BinPNG.TileSkybox(FullBox,x,y,tilepath)
		FullBox.save(str(SB / (name+'.png')))
		[os.remove(Path(img.name)) for img in imgs]
		print('skybox %s done'%name)
	print('skyboxes done')
	ExportSeg2(rom,Textures,s)

#segment 2
def ExportSeg2(rom,Textures,s):
	Seg2 = Textures/'segment2'
	Seg2.mkdir(exist_ok=True)
	#seg2 textures have a few sections. First is 16x16 HUD glyphs. 0x200 each
	nameOff=0
	for tex in range(0,0x4A00,0x200):
		if tex in Seg2Glpyhs:
			nameOff+=Seg2Glpyhs[tex]
		gname = 'segment2.{:05X}.rgba16'.format(tex+nameOff)
		glyph = BinPNG.MakeImage(str(Seg2 / gname))
		loc = s.B2P(0x02000000+tex)
		bin = rom[loc:loc+0x200]
		BinPNG.RGBA16(16,16,bin,glyph)
	#cam glyphs are separate
	nameOff=0xb50
	for tex in range(0x7000,0x7600,0x200):
		gname = 'segment2.{:05X}.rgba16'.format(tex+nameOff)
		glyph = BinPNG.MakeImage(str(Seg2 / gname))
		loc = s.B2P(0x02000000+tex)
		bin = rom[loc:loc+0x200]
		BinPNG.RGBA16(16,16,bin,glyph)
	#cam up/down are 8x8
	for tex in range(0x7600,0x7700,0x80):
		gname = 'segment2.{:05X}.rgba16'.format(tex+nameOff)
		glyph = BinPNG.MakeImage(str(Seg2 / gname))
		loc = s.B2P(0x02000000+tex)
		bin = rom[loc:loc+0x80]
		BinPNG.RGBA16(8,8,bin,glyph)
	#Now exporting dialog chars. They are 16x8 IA4. 0x40 in length each.
	for char in range(0x5900,0x7000,0x40):
		gname = 'font_graphics.{:05X}.ia4'.format(char)
		glyph = BinPNG.MakeImage(str(Seg2 / gname))
		loc = s.B2P(0x02000000+char)
		bin = rom[loc:loc+0x40]
		BinPNG.IA(16,8,4,bin,glyph)
	#now credits font. Its 8x8 rgba16, 0x80 length each
	nameOff=0x6200-0x4A00
	for char in range(0x4A00,0x5900,0x80):
		#the names are offset from actual loc
		gname = 'segment2.{:05X}.rgba16'.format(char+nameOff)
		glyph = BinPNG.MakeImage(str(Seg2 / gname))
		loc = s.B2P(0x02000000+char)
		bin = rom[loc:loc+0x80]
		BinPNG.RGBA16(8,8,bin,glyph)
	#shadows. 16x16 IA8. 0x100 len
	names = ['shadow_quarter_circle','shadow_quarter_square']
	for char in range(2):
		gname = '{}.ia4'.format(names[char])
		glyph = BinPNG.MakeImage(str(Seg2 / gname))
		loc = s.B2P(0x02000000+char*0x100+0x120b8)
		bin = rom[loc:loc+0x100]
		BinPNG.IA(16,16,8,bin,glyph)
	#warp transitions. 32x64 or 64x64. I will grab data from arr for these
	for warp in Seg2WarpTransDat:
		gname = 'segment2.{}.ia4'.format(warp[1])
		glyph = BinPNG.MakeImage(str(Seg2 / gname))
		loc = s.B2P(0x02000000+warp[0])
		bin = rom[loc:loc+warp[3]]
		BinPNG.IA(*warp[2],8,bin,glyph)
	#last in seg2 is water boxes. These are all rgba16 32x32 except mist which is IA16
	nameOff=0x11c58-0x14AB8
	for tex in range(5):
		TexLoc = (tex*0x800+0x14AB8)
		if tex==3:
			gname = 'segment2.{:05X}.ia16'.format(TexLoc+nameOff)
		else:
			gname = 'segment2.{:05X}.rgba16'.format(TexLoc+nameOff)
		glyph = BinPNG.MakeImage(str(Seg2 / gname))
		loc = s.B2P(0x02000000+TexLoc)
		bin = rom[loc:loc+0x800]
		if tex==3:
			BinPNG.IA(32,32,16,bin,glyph)
		else:
			BinPNG.RGBA16(32,32,bin,glyph)

#Rip misc data that may or may not need to be ported. This currently is trajectories and star positions.
#Do this if misc or 'all' is called on a rom.
def ExportMisc(rom,rootdir,editor):
	s = Script(9)
	misc = rootdir/'src'/'game'
	os.makedirs(misc,exist_ok=True)
	StarPos = misc/('Star_Pos.inc.c')
	Trajectory = misc/('Trajectories.inc.c')
	#Trajectories are by default in the level bank, but moved to vram for all hacks
	#If your trajectory does not follow this scheme, then too bad
	Trj = open(Trajectory,'w')
	Trj.write("""#include <PR/ultratypes.h>
#include "level_misc_macros.h"
#include "macros.h"
#include "types.h""
""")
	for k,v in Trajectories.items():
		Dat = UPA(rom,v,'>L',4)[0]
		#Check if Dat is in a segment or not
		if Dat>>24!=0x80:
			Trj.write('//%s Has the default vanilla value or an unrecognizable pointer\n\n'%k)
			Trj.write(DefaultTraj[k])
		else:
			Trj.write('const Trajectory {}_path[] = {{\n'.format(k))
			Dat = Dat-0x7F200000
			x=0
			while(True):
				point = UPA(rom,Dat+x,'>4h',8)
				if point[0]==-1:
					break
				Trj.write('\tTRAJECTORY_POS({},{},{},{}),\n'.format(*point))
				x+=8
			Trj.write('\tTRAJECTORY_END(),\n};\n')
	#Star positions
	SP = open(StarPos,'w')
	#pre editor and post editor do star positions completely different.
	#I will only be supporting post editor as the only pre editor hack people care
	#about is sm74 which I already ported.
	for k,v in StarPositions.items():
		#different loading schemes for depending on if a function or array is used for star pos
		if v[0]:
			pos = [UPA(rom,a[1],a[0],a[2])[0] for a in v[:-2]]
			SP.write("#define {}StarPos {} {}, {}, {} {}\n".format(k,v[-2],*pos,v[-1]))
		else:
			if editor:
				pos = UPF(rom,v[2])
			else:
				pos = UPF(rom,v[1])
			if UPA(rom,v[1],">L",4)[0]==0x01010101:
				SP.write(DefaultPos[k])
			else:
				SP.write("#define {}StarPos {}f, {}f, {}f\n".format(k,*pos))
	#item box. In editor its at 0xEBA0 same as vanilla, RM is at 0x1204000
	#the struct is 4*u8 (id, bparam1, bparam2, model ID), bhvAddr u32
	if editor:
		ItemBox = 0xEBBA0
	else:
		ItemBox = 0x1204000
	IBox = misc/('Item_Box.inc.c')
	IBox = open(IBox,'w')
	IBox.write("""#include <PR/ultratypes.h>
#include "behavior_actions.h"
#include "macros.h"
#include "types.h"
#include "behavior_data.h"
""")
	IBox.write('struct Struct802C0DF0 sExclamationBoxContents[] = { ')
	while(True):
		B = UPA(rom,ItemBox,">4B",4)
		if B[0]==99:
			break
		Bhv = s.GetLabel("{:08x}".format(UPA(rom,ItemBox+4,">L",4)[0]))
		ItemBox+=8
		IBox.write("{{ {}, {}, {}, {}, {} }},\n".format(*B,Bhv))
	IBox.write("{ 99, 0, 0, 0, NULL } };\n")
	ExportTweaks(rom,rootdir)

#This gets exported with misc, but is a separate function
def ExportTweaks(rom,rootdir):
	misc = rootdir/'src'/'game'
	os.makedirs(misc,exist_ok=True)
	twk = open(misc/'tweak.inc.c','w')
	twk.write("""//This is a series of defines to edit commonly changed parameters in romhacks
//These are commonly referred to as tweaks
""")
	for tweak in Tweaks:
		len = tweak[0]
		res = []
		for i in range(len):
			#type,len,offset,func
			arr = tweak[2][i*4:i*4+4]
			#UPA(rom, offset, type, len)
			res.append(arr[3](UPA(rom,arr[2],arr[0],arr[1])))
		val = repr(res)[1:-1].replace("'","")
		twk.write('#define {} {}\n'.format(tweak[1],val))
	#Stuff idk how/haven't gotten to yet in rom but is still useful to have as a tweak
	twk.write(unkDefaults)
	twk.close()

def AsciiConvert(num):
	#numbers start at 0x30
	if num<10:
		return chr(num+0x30)
	#capital letters start at 0x41
	elif num<0x24:
		return chr(num+0x37)
	#lowercase letters start at 0x61
	elif num<0x3E:
		return chr(num+0x3D)
	else:
			return TextMap[num]

#seg 2 is mio0 compressed which means C code doesn't translate to whats in the rom at all.
#This basically means I have to hardcode offsets, it should work for almost every rom anyway.
def ExportText(rom,rootdir,TxtAmt):
	s = Script(9)
	s.Seg2(rom)
	DiaTbl = s.B2P(0x0200FFC8)
	text = rootdir/"text"/'us'
	os.makedirs(text,exist_ok=True)
	textD = text/("dialogs.h")
	textD = open(textD,'w',encoding="utf-8")
	UPW = (lambda x,y: struct.unpack(">L",x[y:y+4])[0])
	#format is u32 unused, u8 lines/box, u8 pad, u16 X, u16 width, u16 pad, offset
	DialogFmt = "int:32,2*uint:8,3*uint:16,uint:32"
	for dialog in range(0,TxtAmt*16,16):
		StrSet = BitArray(rom[DiaTbl+dialog:DiaTbl+16+dialog])
		StrSet = StrSet.unpack(DialogFmt)
		#mio0 compression messes with banks and stuff it just werks
		Mtxt = s.B2P(StrSet[6])
		str = ""
		while(True):
			num = rom[Mtxt:Mtxt+1][0]
			if num!=0xFF:
				str+=AsciiConvert(num)
			else:
				break
			Mtxt+=1
		textD.write('DEFINE_DIALOG(DIALOG_{0:03d},{1:d},{2:d},{3:d},{4:d}, _("{5}"))\n\n'.format(int(dialog/16),StrSet[0],StrSet[1],StrSet[3],StrSet[4],str))
	textD.close()
	#now do courses
	courses = text/("courses.h")
	LevelNames = 0x8140BE
	courses = open(courses,'w',encoding="utf-8")
	for course in range(26):
		name = s.B2P(UPW(rom,course*4+LevelNames))
		str = ""
		while(True):
			num = rom[name:name+1][0]
			if num!=0xFF:
				str+=AsciiConvert(num)
			else:
				break
			name+=1
		acts = []
		ActTbl = 0x814A82
		if course<15:
			#get act names
			for act in range(6):
				act = s.B2P(UPW(rom,course*24+ActTbl+act*4))
				Actstr=""
				while(True):
					num = rom[act:act+1][0]
					if num!=0xFF:
						Actstr+=AsciiConvert(num)
					else:
						break
					act+=1
				acts.append(Actstr)
			courses.write("COURSE_ACTS({}, _(\"{}\"),\t_(\"{}\"),\t_(\"{}\"),\t_(\"{}\"),\t_(\"{}\"),\t_(\"{}\"),\t_(\"{}\"))\n\n".format(Course_Names[course],str,*acts))
		elif course<25:
			courses.write("SECRET_STAR({}, _(\"{}\"))\n".format(course,str))
		else:
			courses.write("CASTLE_SECRET_STARS(_(\"{}\"))\n".format(str))
	#do extra text
	Extra = 0x814A82+15*6*4
	for i in range(7):
		Ex=s.B2P(UPW(rom,Extra+i*4))
		str=""
		while(True):
			num = rom[Ex:Ex+1][0]
			if num!=0xFF:
				str+=AsciiConvert(num)
			else:
				break
			Ex+=1
		courses.write("EXTRA_TEXT({},_(\"{}\"))\n".format(i,str))
	courses.close()

def ExportWaterBoxes(AllWaterBoxes,rootdir):
	misc = rootdir/'src'/'game'
	os.makedirs(misc,exist_ok=True)
	MovtexEdit = misc/"moving_texture.inc.c"
	infoMsg = """#include <ultra64.h>
#include "sm64.h"
#include "moving_texture.h"
#include "area.h"
/*
This is an include meant to help with the addition of moving textures for water boxes. Moving textures are hardcoded in vanilla, but in hacks they're procedural. Every hack uses 0x5000 +Type (0 for water, 1 for toxic mist, 2 for mist) to locate the tables for their water boxes. I will replicate this by using a 3 dimensional array of pointers. This wastes a little bit of memory but is way easier to manage.
To use this, simply place this file inside your source directory after exporting.
*/
"""
	if not AllWaterBoxes:
		print("no water boxes")
		return
	MTinc = open(MovtexEdit,'w')
	MTinc.write(infoMsg)
	for a in AllWaterBoxes:
		MTinc.write("extern u8 "+a[0]+"[];\n")
	MTinc.write("\nstatic void *RM2C_Water_Box_Array[33][8][3] = {\n")
	AreaNull = "{"+"NULL,"*3+"},"
	LevelNull = "{ "+AreaNull*8+" },\n"
	LastL = 3
	LastA = 0
	LastType=0
	first = 0
	for wb in AllWaterBoxes:
		L = wb[1]
		A = wb[2]
		T = wb[3]
		if (A!=LastA or L!=LastL) and first!=0:
			for i in range(2-LastType):
				MTinc.write("NULL,")
			MTinc.write("},")
		if L!=LastL and first!=0:
			LastType = 0
			for i in range(7-LastA):
				MTinc.write(AreaNull)
			LastA = 0
			MTinc.write(" },\n")
		for i in range(L-LastL-1):
			MTinc.write(LevelNull)
		if first==0 or L!=LastL:
			MTinc.write("{ ")
		for i in range(A-LastA):
			MTinc.write(AreaNull)
		for i in range(T-LastType):
			MTinc.write("NULL,")
		if T==0:
			MTinc.write("{")
		MTinc.write("&%s,"%wb[0])
		LastL = L
		LastA = A
		LastType = T
		first=1
	for i in range(2-LastType):
		MTinc.write("NULL,")
	MTinc.write("},")
	for i in range(7-LastA):
		MTinc.write(AreaNull)
	MTinc.write(" }\n};\n")
	func = """
void *GetRomhackWaterBox(u32 id){
id = id&0xF;
return RM2C_Water_Box_Array[gCurrLevelNum-4][gCurrAreaIndex][id];
};"""
	MTinc.write(func)

if __name__=='__main__':
	HelpMsg="""
------------------Invalid Input - Error ------------------

Arguments for RM2C are as follows:
RM2C.py, rom="romname", editor=False, levels=[] (or levels='all'), actors=[] (or assets='all'), Append=[(rom,areaoffset,editor),...] WaterOnly=0 ObjectOnly=0 MusicOnly=0 MusicExtend=0 Text=0 Misc=0 Textures=0 Inherit=0 Upsacle=0

Arguments with equals sign are shown in default state, do not put commas between args.
Levels accept any list argument or only the string 'all'. Append is for when you want to combine multiple roms. The appended roms will be use the levels of the original rom, but use the areas of the appended rom with an offset. You must have at least one level to export assets because the script needs to read the model load cmds to find pointers to data.
Actors will accept either a list of modelIDs, a string for a group (see decomp group folders e.g. common0, group1 etc.) the string 'all' for all models, or the string 'new' for only models without a known label.
The "Only" options are to only export certain things either to deal with specific updates or updates to RM2C itself. Only use one at a time. An only option will not maintain other data. Do not use Append with MusicOnly, it will have no effect.
MusicExtend is for when you want to add in your custom music on top of the original tracks. Set it to the amount you want to offset your tracks by (0x23 for vanilla).
Textures will export the equivalent of the /textures/ folder in decomp.
Inherit is a file management arg for when dealing with multiple roms. Normal behavior is to clear level folder each time, inherit prevents this.
Upscale is an option to use ESRGAN ai upscaling to increase texture size. The upscaled textures will generate #ifdefs in each model file for non N64 targeting to compile them instead of the original textures.

Example input1 (all actor models in BoB):
python RM2C.py rom="ASA.z64" editor=True levels=[9] actors='all'

Example input2 (Export all Levels in a RM rom):
python RM2C.py rom="baserom.z64" levels='all'

Example input3 (Export all BoB in a RM rom with a second area from another rom):
python RM2C.py rom="baserom.z64" levels='all' Append=[('rom2.z64',1,True)]

NOTE! if you are on unix bash requires you to escape certain characters. For this module, these
are quotes and paranthesis. Add in a escape before each.

example: python3 RM2C.py rom=\'sm74.z64\' levels=[9] Append=[\(\'sm74EE.z64\',1,1\)] editor=1

A bad input will automatically generate an escaped version of your args, but it cannot do so before
certain bash errors.
------------------Invalid Input - Error ------------------
"""
	#set default arguments
	levels=[]
	actors=[]
	editor=False
	rom=''
	Append=[]
	args = ""
	WaterOnly = 0
	ObjectOnly = 0
	MusicOnly = 0
	MusicExtend = 0
	Text = 0
	Misc=0
	Textures=0
	Inherit=0
	Upscale=0
	#This is not an arg you should edit really
	TxtAmount = 170
	for arg in sys.argv[1:]:
		args+=arg+" "
	a = "\\".join(args)
	a = "python3 RM2C.py "+a
	try:
		#the utmosts of cringes
		for arg in sys.argv:
			if arg=='RM2C.py':
				continue
			arg=arg.split('=')
			locals()[arg[0]]=eval(arg[1])
	except:
		print(HelpMsg)
		print("If you are using terminal try using this\n"+a)
		raise 'bad arguments'
	romname = rom.split(".")[0]
	rom=open(rom,'rb')
	rom = rom.read()
	#Export dialogs and course names
	if Text or levels=='all':
		for A in Append:
			Arom = open(A[0],'rb')
			Arom = Arom.read()
			ExportText(Arom,Path(sys.path[0]),TxtAmount)
		ExportText(rom,Path(sys.path[0]),TxtAmount)
		print('Text Finished')
	#Export misc data like trajectories or star positions.
	if Misc or levels=='all':
		for A in Append:
			Arom = open(A[0],'rb')
			Arom = Arom.read()
			ExportMisc(Arom,Path(sys.path[0]),A[2])
		ExportMisc(rom,Path(sys.path[0]),editor)
		print('Misc Finished')
	print('Starting Export')
	AllWaterBoxes = []
	m64s = []
	seqNums = []
	Onlys = [WaterOnly,ObjectOnly,MusicOnly]
	#custom level defines file so the linker knows whats up. Mandatory or export won't work
	lvldefs = Path(sys.path[0]) / 'levels'
	#So you don't have truant level folders from a previous export
	if not Inherit:
		if os.path.isdir(lvldefs):
			shutil.rmtree(lvldefs)
	lvldefs.mkdir(exist_ok=True)
	lvldefs = lvldefs/"custom_level_defines.h"
	lvldefs = open(lvldefs,'w')
	ass=Path("actors")
	ass=Path(sys.path[0])/ass
	ass.mkdir(exist_ok=True)
	#Array of all scripts from each level
	Scripts = []
	if levels=='all':
		for k in Num2Name.keys():
			Scripts.append(ExportLevel(rom,k,editor,Append,AllWaterBoxes,Onlys,romname,m64s,seqNums,MusicExtend,lvldefs))
			print(Num2Name[k] + ' done')
	else:
		for k in levels:
			if not Num2Name.get(k):
				continue
			Scripts.append(ExportLevel(rom,k,editor,Append,AllWaterBoxes,Onlys,romname,m64s,seqNums,MusicExtend,lvldefs))
			print(Num2Name[k] + ' done')
	lvldefs.close()
	#Process returned scripts to view certain custom data such as custom banks/actors for actor/texture exporting
	[Banks,Models] = ProcessScripts(rom,editor,Scripts)
	ExportActors(actors,rom,Banks,Models,editor)
	#export textures
	if Textures:
		ExportTextures(rom,editor,Path(sys.path[0]),Banks)
	#AllWaterBoxes should have refs to all water boxes, using that, I will generate a function
	#and array of references so it can be hooked into moving_texture.c
	#example of AllWaterBoxes format [[str,level,area,type]...]
	if not (MusicOnly or ObjectOnly):
		ExportWaterBoxes(AllWaterBoxes,Path(sys.path[0]))
	if not (WaterOnly or ObjectOnly):
		CreateSeqJSON(romname,list(zip(m64s,seqNums)),Path(sys.path[0]),MusicExtend)
	print('Export Completed')