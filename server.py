import os, sys
import threading
import time

import Pyro4

class NameServer (object):

    def __init__ (self):
        try:
            self.ns = Pyro4.naming.locateNS ()
        except Pyro4.errors.NamingError:
            self.event = threading.Event ()
            self.event.set ()
            self.thread = threading.Thread (target=self.run_nameserver)
            self.thread.start ()
            self.ns = Pyro4.naming.locateNS ()
        else:
            self.event = self.thread = None

    def __getattr__ (self, attr):
        return getattr (self.ns, attr)

    def run_nameserver (self):
        uri, daemon, bc_server = Pyro4.naming.startNS ()
        daemon.requestLoop (self.event.isSet)
        print "Finished daemon"

    def finish (self):
        print "About to finish"
        if self.thread:
            self.event.clear ()
            print "event cleared"
            self.thread.join ()
            print "thread joined"

def main ():
    ns = NameServer ()
    print ns.list ()
    ns.finish ()

if __name__ == '__main__':
    main (*sys.argv[1:])
