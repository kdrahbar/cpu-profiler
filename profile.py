#!/usr/bin/python
import psutil 
import re
import pika
import signal
import time
import sys

# Add commas to floats
def commify3(amount):
  amount = str(amount)
  amount = amount[::-1]
  amount = re.sub(r"(\d\d\d)(?=\d)(?!\d*\.)", r"\1,", amount)
  return amount[::-1]

def bytes2human(n):
   symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
   prefix = {}
   for i, s in enumerate(symbols):
      prefix[s] = 1 << (i + 1) * 10
   for s in reversed(symbols):
      if n >= prefix[s]:
         value = float(n) / prefix[s]
         return '%.2f %s' % (value, s)
   return '%.2f B' % (n)

class CpuProfiler:

  def __init__(self, connection, target_os):
    self.mem = psutil.virtual_memory()
    self.swap = psutil.swap_memory()
    self.perc = psutil.cpu_times_percent(interval=0.5, percpu=False)
    self.connection = connection
    self.channel = self.connection.channel()
    self.channel.queue_declare(queue='proc_info')
    self.target_os = target_os.lower()
    self.message = ""

  # Collects info about memory usage and puts into the message buffer
  def get_mem_info(self):
    used = self.mem.total - self.mem.available;
    mb_used = str(int(used / 1024 / 1024)) + "MiB";
    mb_total = str(int(self.mem.total / 1024 / 1024)) + "MiB";
    mem_used_vs_total = commify3(mb_used) + "/" + commify3(mb_total)
    
    mem_info = ("\nMemory:                %10s   (used)/(total)" % (mem_used_vs_total) + '\n'
                "Memory Total:     %10sM" % (commify3(str(int(self.mem.total / 1024 / 1024)))) + '\n'
                "Memory Available: %10sM" % (commify3(str(int(self.mem.available / 1024 / 1024)))) + '\n'
                "Memory Percent:  %10s" % (str(self.mem.percent)) + "%" + '\n'
                "Memory used:      %10sM" % (commify3(str(int(self.mem.used / 1024 / 1024)))) + '\n'
                "Memory free:      %10sM" % (commify3(str(int(self.mem.free / 1024 / 1024)))) + '\n')
    
    if self.target_os == "linux":
      mem_info += ("Memory active:    %10sM" % (commify3(str(int(mem.active / 1024 / 1024)))) + '\n'
                   "Memory inactive:  %10sM" % (commify3(str(int(mem.inactive/ 1024 / 1024)))) + '\n'
                   "Memory buffers:   %10sM" % (commify3(str(int(mem.buffers / 1024 / 1024)))) + '\n'
                   "Memory cached:    %10sM" % (commify3(str(int(mem.cached / 1024 / 1024)))) + '\n')

    self.message += mem_info

  # Collects info about swap space usage and puts into the message buffer
  def get_swap_info(self):
    swap_used = str(int(self.swap.used / 1024 / 1024)) + "M";
    swap_total = str(int(self.swap.total / 1024 / 1024)) + "M";
    swap_used_vs_total = commify3(swap_used) + "/" + commify3(swap_total);

    self.message += ("\nSwap Space:            %10s (used)/(total)" % (swap_used_vs_total) + '\n'
                    "Swap Total:       %10sM" % (commify3(str(int(self.swap.total / 1024 / 1024)))) + '\n'
                    "Swap Used:        %10sM" % (commify3(str(int(self.swap.used / 1024 / 1024)))) + '\n'
                    "Swap Free:        %10sM" % (commify3(str(int(self.swap.free / 1024 / 1024)))) + '\n'
                    "Swap Percentage: %10s" % (str(self.swap.percent)) + "%" + '\n'
                    "Swap sin:         %10sM" % (commify3(str(int(self.swap.sin / 1024 / 1024)))) + '\n'
                    "Swap sout:        %10sM" % (commify3(str(int(self.swap.sout / 1024 / 1024)))) + '\n' )

  def get_network_info(self):
    t1 = psutil.net_io_counters()
    
    interval = 0.2;
    time.sleep(interval)
    
    t2 = psutil.net_io_counters()
    
    self.message += ( "\nBytes-sent per second: %5s" % (bytes2human(t2.bytes_sent - t1.bytes_sent)) + '\n'
                      "Bytes-recv per second: %5s" % (bytes2human(t2.bytes_recv - t1.bytes_recv)) + '\n'
                      "Pkts-sent per second:  %5s" % (bytes2human(t2.packets_sent - t1.packets_sent)) + '\n'
                      "Pkts-recv per second:  %5s" % (bytes2human(t2.packets_recv - t1.packets_recv)) ) + '\n'
     
  def get_cpu_info(self):
    cpu_info = ("\nUser:    %5s%%  nice:  %5s%%" % (self.perc.user, self.perc.nice) + '\n'
                "System:  %5s%%  idle:  %5s%%  " % (self.perc.system, self.perc.idle) + '\n')
    
    if self.target_os == "linux":
      cpu_info = ("iowait:  %5s%%  irq:   %5s%% " % (self.perc.iowait, self.perc.irq) + '\n'
                  "softirq: %5s%%  steal: %5s%% " % (self.perc.softirq, self.perc.steal) + '\n'
                  "guest:   %5s%% " % (self.perc.guest) + '\n')
    self.message += cpu_info 
  
  # @param frequency: the rate at which to sample cpu info
  def run(self, frequency):
    while True: 
      self.get_mem_info()
      self.get_swap_info()
      self.get_network_info()
      self.get_cpu_info()
      self.channel.basic_publish(exchange='',
                        routing_key='proc_info',
                        body=self.message)
      print "[x] Sent the following message\n"
      print self.message
      self.message = ""
      
      time.sleep(frequency)
 
def signal_int_handler(signal, frame):
    print "attempting to shutdown"
    connection.close()
    sys.exit(0)

if __name__ == '__main__':
  signal.signal(signal.SIGINT, signal_int_handler)
  connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
  cpu_prof = CpuProfiler(connection, "osx")
  cpu_prof.run(3)