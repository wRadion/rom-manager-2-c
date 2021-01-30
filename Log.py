#This module is meant to do cross module logging of stuff to look out for when importing to decomp
#and also go give general warnings and instructions for people who don't know much
import sys
from RM2CData import *

log = sys.path[0]

log = open(log+'//ImportInstructions.py','w')

log.write("""This file will contain instructions on how to import RM2C data into the sm64ex-alo repo.
First you should always copy the exported folders (/src,/levels,/sound,/text,/textures,/actors) into your repo.
Then make sure you set RM2C inside the makefile to 1
Then to build for PC use this input to terminal: "make clean && make -j4 TARGET_N64=0 TARGET_ARCH=native WINDOWS_BUILD=1 TARGET_GAME_CONSOLE=0 DEBUG=1 NODRAWINGDISTANCE=1"
Then to build for N64 use this input to terminal: "make clean && make -j4"
By default, due to their high variability and unique names, no actor data will be included from RM2C output, you must
go per actor and either copy data from a custom.model.inc.c file to the model.inc.c file, or change the includes in group files.

Level specific models will go into a folder inside of /actors/ with the name of the level they belong to. You must copy these folders
over to their level folders. The directory should match the target level dir, and not overwrite any files. Textures should be pre written
to the target level directories.

Below are some warnings generated by RM2C during extraction.
It is expected to have many warnings for editor files and for roms with lots of custom content.

""")

Spacer="*"*90

BadScroll=[]
Scrollerrs=[]
def InvalidScroll(level,area,scroll):
	global BadScroll
	global Scrollerrs
	if (level,area,scroll) in BadScroll:
		return
	else:
		BadScroll.append((level,area,scroll))
		err = 'Texture Scroll Object in level {} area {} at {} likely has a bad address.\n'.format(Num2Name[level],area,hex(scroll[2]))
		print(err)
		Scrollerrs.append(err)

LastFog=[]
Fogerrs=[]
def LevelFog(level,DL):
	global LastFog
	global Fogerrs
	print(level,DL)
	if (level,DL) in LastFog:
		return
	else:
		LastFog.append((level,DL))
		err = 'Level {} Display List {} has fog, high potential for broken graphics.\n'.format(Num2Name[level],DL)
		print(err)
		Fogerrs.append(err)

UnkObjs = []
Objerrs=[]
def UnkObject(level,Area,bhv):
	global UnkObjs
	global Objerrs
	if (level,Area,bhv) in UnkObjs:
		return
	else:
		UnkObjs.append((level,Area,bhv))
		err = 'Level {} Area {} has object {} with no known label.\n'.format(Num2Name[level],Area,bhv)
		print(err)
		Objerrs.append(err)

def WriteWarnings():
	global Objerrs
	global Fogerrs
	global Scrollerrs
	if Objerrs:
		log.write(Spacer+"\n\nObjects without references must have behaviors created for them, be given an existing behavior, or be commented out.\n")
		[log.write(' {}'.format(s)) for s in Objerrs]
	if Fogerrs:
		log.write(Spacer+"\n\nLevels with fog in sm64 editor and likely early versions of Rom Manager are completely broken and destroy the levels graphics and most non opaque objects.\nYou will need to either remove the fog, or manually fix the fog DLs in these levels (Unless you trust the importer).\n\n")
		[log.write(' {}'.format(s)) for s in Fogerrs]
	if Scrollerrs:
		log.write(Spacer+"\n\nTexture scrolls do not always follow the same format I assume, if this error appears it may have an invalid address which causes a crash.\nRM2C will try to find the correct address after noticing the one it has is wrong, if a crash occurs when entering the level check these objects first\n\n")
		[log.write(' {}'.format(s)) for s in Scrollerrs]
	log.write(Warnings)
	log.close()

Warnings = """
Known methods of crashing:
*****************************************************************************
ALL BUILDS
IF CRASH ON BOOT - CHECK SEQUENCES
IF TITLE SCREEN LOOP - CHECK START LEVEL IN TWEAKS.INC.C
IF TEXTURES ARE MESSED UP - ALWAYS CHECK LEVEL FOG FIRST
IF CRASH UPON ENTERING A LEVEL, CHECK OBJECTS. IF EDITOR, CHECK SCROLLS FIRST. IF NO OBJECTS BAD CHECK SEQUENCES
*****************************************************************************
N64 BUILD
IF SURFACE NODE POOOL OR SURFACE POOL FULL - ADD MORE TRIS TO EXT BOUNDS.H
IF CRASH ON STAR SELECT - PUSH FORWARD GODDARD SEGMENT IN SEGMENTS.H
*****************************************************************************
"""