#!/usr/bin/env python
import pika

def callback(ch, method, properties, body):
    print " [x] Received %s" % (body)


# if __name__ == '__main__':
connection = pika.BlockingConnection(pika.ConnectionParameters(
        host='localhost'))
channel = connection.channel()
channel.queue_declare(queue='proc_info')

print ' [*] Waiting for messages. To exit press CTRL+C'

channel.basic_consume(callback,
                      queue='proc_info',
                      no_ack=True)

channel.start_consuming()