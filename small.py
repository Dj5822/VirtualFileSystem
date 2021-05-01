#!/usr/bin/env python
from __future__ import print_function, absolute_import, division

import logging
import disktools

from collections import defaultdict
from errno import ENOENT
from stat import S_IFDIR, S_IFLNK, S_IFREG
from time import time

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

import format
import os

if not hasattr(__builtins__, 'bytes'):
    bytes = str

def get_file_name(block_num):
    return disktools.read_block(block_num)[22:38].decode()

class Small(LoggingMixIn, Operations):
    'Example memory filesystem. Supports only one level of files.'

    """
    The disk will contain the file attributes and the file data.
    We can store the file attributes in the first 4 blocks.
    We can store the file data in the other 12 blocks.
    """
    def __init__(self):
        self.fd = 0
        # Find out which blocks are empty and which are full.
        for i in range(len(format.empty_file_block_list)):
            if disktools.bytes_to_int(disktools.read_block(i)[18:19]) != 0:
                format.empty_file_block_list[i] = False

    def chmod(self, path, mode):
        if (path == "/"):
            file_name = "/"
        else:
            file_name = os.path.basename(path)
        
        # find the file that we are trying to write to.
        for i in range(len(format.empty_file_block_list)):
            if disktools.read_block(i)[22:22+len(file_name)].decode() == file_name:
                block = disktools.read_block(i)
                value = disktools.bytes_to_int(block[0:2]) & 0o770000
                block[0:2] = disktools.int_to_bytes(value | mode, 2)
                disktools.write_block(i, block)
                break      

        return 0

    def chown(self, path, uid, gid):
        if (path == "/"):
            file_name = "/"
        else:
            file_name = os.path.basename(path)

        print(disktools.read_block(0))
        
        # find the file that we are trying to write to.
        for i in range(len(format.empty_file_block_list)):
            if disktools.read_block(i)[22:22+len(file_name)].decode() == file_name:
                block = disktools.read_block(i)
                block[2:4] = disktools.int_to_bytes(uid, 2)
                block[4:6] = disktools.int_to_bytes(gid, 2)
                disktools.write_block(i, block)
                break

        print(disktools.read_block(0))

    # adds a new file by adding file attributes to the files dictionary.
    # whenever a file is created, fd will be incremented and returned (fd is basically the id for the file).
    # mode is the permissions that you want the file to have.
    def create(self, path, mode):
        self.files[path] = dict(
            st_mode=(S_IFREG | mode),
            st_nlink=1,
            st_size=0,
            # set create, modify, access times to the current time.
            st_ctime=time(),
            st_mtime=time(),
            st_atime=time(),
            st_uid=1000,
            st_gid=1000)

        self.fd += 1
        return self.fd

    # if the file exists, then it will return the attributes of the file.
    def getattr(self, path, fh=None):
        if path not in self.files:
            raise FuseOSError(ENOENT)

        return self.files[path]

    def getxattr(self, path, name, position=0):
        attrs = self.files[path].get('attrs', {})

        try:
            return attrs[name]
        except KeyError:
            return ''       # Should return ENOATTR

    def listxattr(self, path):
        attrs = self.files[path].get('attrs', {})
        return attrs.keys()
    # similar to create, however the number of st_nlink is 2 instead of 1.
    def mkdir(self, path, mode):
        self.files[path] = dict(
            st_mode=(S_IFDIR | mode),
            st_nlink=2,
            st_size=0,
            st_ctime=time(),
            st_mtime=time(),
            st_atime=time())

        self.files['/']['st_nlink'] += 1

    # passes the file path of the file that you want open and increment the file descriptor.
    def open(self, path, flags):
        self.fd += 1
        return self.fd

    # starts reading from the offset until offset + size.
    def read(self, path, size, offset, fh):
        return self.data[path][offset:offset + size]

    def readdir(self, path, fh):
        return ['.', '..'] + [x[1:] for x in self.files if x != '/']

    def readlink(self, path):
        return self.data[path]

    def removexattr(self, path, name):
        attrs = self.files[path].get('attrs', {})

        try:
            del attrs[name]
        except KeyError:
            pass        # Should return ENOATTR

    def rename(self, old, new):
        self.data[new] = self.data.pop(old)
        self.files[new] = self.files.pop(old)

    def rmdir(self, path):
        # with multiple level support, need to raise ENOTEMPTY if contains any files
        self.files.pop(path)
        self.files['/']['st_nlink'] -= 1

    def setxattr(self, path, name, value, options, position=0):
        # Ignore options
        attrs = self.files[path].setdefault('attrs', {})
        attrs[name] = value

    def statfs(self, path):
        return dict(f_bsize=512, f_blocks=4096, f_bavail=2048)

    def symlink(self, target, source):
        self.files[target] = dict(
            st_mode=(S_IFLNK | 0o777),
            st_nlink=1,
            st_size=len(source))

        self.data[target] = source

    def truncate(self, path, length, fh=None):
        # make sure extending the file fills in zero bytes
        self.data[path] = self.data[path][:length].ljust(
            length, '\x00'.encode('ascii'))
        self.files[path]['st_size'] = length

    def unlink(self, path):
        self.data.pop(path)
        self.files.pop(path)

    def utimens(self, path, times=None):
        now = time()
        atime, mtime = times if times else (now, now)
        self.files[path]['st_atime'] = atime
        self.files[path]['st_mtime'] = mtime

    # receives the file path, data, and offset.
    # modifies the file data such that it removes everything after the offset
    # and replaces it with the new data.
    # file size will also be updated.
    def write(self, path, data, offset, fh):
        self.data[path] = (
            # make sure the data gets inserted at the right offset
            self.data[path][:offset].ljust(offset, '\x00'.encode('ascii'))
            + data
            # and only overwrites the bytes that data is replacing
            + self.data[path][offset + len(data):])
        self.files[path]['st_size'] = len(self.data[path])
        return len(data)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('mount')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    fuse = FUSE(Small(), args.mount, foreground=True)
