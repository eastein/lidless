#!/usr/bin/env python

import time
import os, os.path
import sys
import shutil

KEEP = 7

class Pruner(object) :
	def __init__(self, head_dir, keep=KEEP) :
		self.head_dir = head_dir
		self.keep = keep

	def prune(self) :
		leaves = [os.path.join(self.head_dir, p) for p in os.listdir(self.head_dir)]
		for leaf in leaves :
			self.prune_leaf(leaf, self.keep)

	def prune_leaf(self, leaf, keep) :
		subdirs = os.listdir(leaf)
		subdirs.sort(cmp=lambda a,b: int.__cmp__(int(a), int(b)))
		if len(subdirs) > keep :
			remove = [os.path.join(leaf, sd) for sd in subdirs[0:len(subdirs) - keep]]
			for r in remove :
				if os.path.exists(os.path.join(r, 'frames.idx')) :
					shutil.rmtree(r)
					print 'removed %s' % r
				else :
					print 'did not remove %s, may not be frameidx directory' % r

if __name__ == '__main__' :
	print time.ctime(), "starting"
	p = Pruner(sys.argv[1])
	p.prune()
	print time.ctime(), "ending"
