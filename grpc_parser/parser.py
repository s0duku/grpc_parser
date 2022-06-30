
# https://developers.google.com/protocol-buffers/docs/encoding#optional

from os import stat_result
import struct
import base64


stack = 0

def linux_base64_decode(payload):
    # python base64 ..., only do once
    # res = b''
    
    # while payload:
    #     dbuf = base64.b64decode(payload)
    #     res += dbuf
    #     ebuf = base64.b64encode(dbuf)
    #     payload = payload[len(ebuf.decode('latin')):]

    return base64.b64decode(payload)



class ProtobufParser:
    TYPE_VARINT = 0
    TYPE_64BIT = 1
    TYPE_LENGTH_DELIMITED = 2
    TYPE_START_GROUP = 3
    TYPE_END_GROUP = 4
    TYPE_32BIT = 5

    def __init__(self,data):
        self.buffer = data

    @staticmethod
    def get_msb(bt):
        bt = ord(bt[0])
        return bt >> 7

    @staticmethod
    def need_more_byte(bt):
        if ProtobufParser.get_msb(bt) == 1:
            return True
        else:
            return False

    def eat_bytes(self,num):
        if len(self.buffer) < num:
            raise Exception("No more data to eat")
        data = self.buffer[:num]
        self.buffer = self.buffer[num:]
        return data

    def get_varint(self):
        int_bts = []
        bt = self.eat_bytes(1)
        int_bts.append(bt)
        while self.need_more_byte(bt):
            bt = self.eat_bytes(1)
            int_bts.append(bt)
        
        int_bts.reverse()

        if len(int_bts) > 1:
            for i in range(1,len(int_bts)):
                int_bts[i] = chr(ord(int_bts[i])& 0b01111111) # drop the msb
        
        var = bin(ord(int_bts[0]))[2:] # take first byte

        for bt in int_bts[1:]:
            var += (bin(ord(bt))[2:]).zfill(7) # every byte fill zero

        return int(var,2)

    def get_64bit(self):
        var = self.eat_bytes(8)
        return struct.unpack('<Q',var.encode('latin'))[0]

    def get_32bit(self):
        var = self.eat_bytes(4)
        return struct.unpack('<I',var.encode('latin'))[0]

    def get_key(self):
        var = self.get_varint()
        field_number = var >> 3 # proto define field number
        wire_type = var & (0x1 | 0x1<<1 | 0x1<<2)
        return field_number,wire_type

    
    @staticmethod
    def try_msg(data):
        try:
            parser = ProtobufParser(data)
            msg = parser.parse()
            return msg
        except:
            return None

    @staticmethod
    def try_string(data):
        try:
            msg = data.encode('latin').decode('utf8')
            return msg
        except:
            return None

    
    def get_length_delimited(self):
        # actualy only the client which has the target '.proto' file
        # can know 'length-delimited' describe what kinds of data (string or embed msg or repeated ...)
        # heuristic method will be used to parse this kind of data
        # so the result may not be accurate

        # https://groups.google.com/g/protobuf/c/0-0LbIwtQeQ, looks like the truth is, we have no choice but to guess what we are facing ...

        length = self.get_varint()
        data = self.eat_bytes(length)

        # first we try to assume it as embed msg
        msg = self.try_msg(data)
        if msg != None:
            return msg
        
        # then may be string UTF-8 ?
        msg = self.try_string(data)
        if msg != None:
            return msg

        # give up for reapted, emm, just hard to determine
        # just assume it as a byte
        
        msg = data
        return msg
    
    def parse(self):
        # msg should always be dict, key-value pair
        msg = {}
        while self.buffer:
            field_number,wire_type = self.get_key()
            if wire_type == self.TYPE_VARINT:
                var = self.get_varint()

            elif wire_type == self.TYPE_LENGTH_DELIMITED:
                var = self.get_length_delimited()
            
            elif wire_type == self.TYPE_64BIT:
                var = self.get_64bit()

            elif wire_type == self.TYPE_32BIT:
                var = self.get_32bit()
            
            # not sure this is right
            # https://stackoverflow.com/questions/33815529/google-protocol-buffer-wire-type-start-group-and-end-group-usage
            # says group should not exist
            # elif wire_type == self.TYPE_START_GROUP:
            #     # print(self.eat_bytes(1))
            #     var = self.parse()

            # elif wire_type == self.TYPE_END_GROUP:
            #     # self.eat_bytes(1)
            #     return msg

            else:
                raise

            # not sure this is right way for dealing repeated field
            new_field_key = '{}:{}'.format(field_number,wire_type)
            if msg.get(new_field_key) != None:
                if isinstance(msg.get(new_field_key),list):
                    msg[new_field_key].append(var)
                else:
                    msg[new_field_key] = [msg[new_field_key]]
                    msg[new_field_key].append(var)
            else:
                msg[new_field_key] = var

        return msg




    def parse_grpc(self):
        self.buffer = linux_base64_decode(self.buffer.encode('latin')).decode('latin')
        
        # with open('TMP','wb') as fd:
        #     fd.write(self.buffer.encode('latin'))

        msgs = []
        res = {'trailer':''}
    
        while self.buffer:
            tag = self.eat_bytes(1)
            if tag == '\x00':
                # data
                data_len = self.eat_bytes(4)
                frame_len = struct.unpack('>I',data_len.encode('latin'))[0]
                frame_data = self.eat_bytes(frame_len)

                # parse protobuf frame
                parser = ProtobufParser(frame_data)
                # with open('TMP','wb') as fd:
                #     fd.write(frame_data.encode('latin'))
                msg = parser.parse()
                if msg == False:
                    return False
                msgs.append(msg)
            elif tag == '\x80':
                # trailer
                data_len = self.eat_bytes(4)
                trailer_len = struct.unpack('>I',data_len.encode('latin'))[0]
                trailer_data = self.eat_bytes(trailer_len)
                res['trailer'] = trailer_data

        res['msgs'] = msgs

        return res


# https://github.com/fmoo/python-varint/blob/master/varint.py

import sys

if sys.version > '3':
    def _byte(b):
        return bytes((b, ))
else:
    def _byte(b):
        return chr(b)

class ProtobufEncoder:

    def __init__(self,grpc):
        self.grpc = grpc
        self.buffer = ''

    @staticmethod
    def set_bit(bt,pos,value):
        if pos < 1:
            raise
        if value:
            # set 1
            tmp = (1 << (pos - 1))
            return bt | tmp
        else:
            # set 0
            tmp = (1 << (pos - 1)) ^ 0xff
            return bt & tmp

    def encode_bytes(self,bt):
        self.buffer += bt

    @staticmethod
    def marshal_varint(number):
        buf = b''
        while True:
            towrite = number & 0x7f
            number >>= 7
            if number:
                buf += _byte(towrite | 0x80)
            else:
                buf += _byte(towrite)
                break
        return buf.decode('latin')

    
    @staticmethod
    def marshal_64bit(number):
        return struct.pack('<Q',number).decode('latin')

    @staticmethod
    def marshal_32bit(number):
        return struct.pack('<I',number).decode('latin')

    def get_key(self):
        var = self.get_varint()
        field_number = var >> 3 # proto define field number
        wire_type = var & (0x1 | 0x1<<1 | 0x1<<2)
        return field_number,wire_type


    @staticmethod
    def marshal_key(field_number,wire_type):
        key = ( field_number << 3 ) | wire_type
        return ProtobufEncoder.marshal_varint(key)

    @staticmethod
    def marshal_length_delimited(msg):
        if isinstance(msg,dict):
            # for msg
            buf = ProtobufEncoder.marshal_msg(msg)
            length = len(buf)
            return ProtobufEncoder.marshal_varint(length) + buf
        else:
            # for string/byte
            length = len(msg)
            return ProtobufEncoder.marshal_varint(length) + msg



    @staticmethod
    def marshal_msg(msg):
        buf = ''

        for field_key,value in msg.items():
            field_number,wire_type = field_key.split(':')
            field_number = int(field_number)
            wire_type = int(wire_type)
            key = ProtobufEncoder.marshal_key(field_number,wire_type)

            buf += key

            if wire_type == ProtobufParser.TYPE_32BIT:
                buf += ProtobufEncoder.marshal_32bit(value)
            elif wire_type == ProtobufParser.TYPE_64BIT:
                buf += ProtobufEncoder.marshal_64bit(value)
            elif wire_type == ProtobufParser.TYPE_VARINT:
                buf += ProtobufEncoder.marshal_varint(value) 
            elif wire_type == ProtobufParser.TYPE_LENGTH_DELIMITED:
                buf += ProtobufEncoder.marshal_length_delimited(value)
            else:
                raise Exception("encoder wire type unknown")

        return buf

    def encode_grpc(self):
        buf = ''
        msgs = self.grpc['msgs']
        trailer = self.grpc['trailer']

        for msg in msgs:
            buf += '\x00'
            data = ProtobufEncoder.marshal_msg(msg)
            length = len(data)
            buf += struct.pack('>I',length).decode('latin')
            buf += data

        if trailer:
            buf += '\x80'
            buf += struct.pack('>I',len(trailer)).decode('latin')
            buf += trailer

        return base64.b64encode(buf.encode('latin')).decode('latin')
            

        






# def DecodeProtobuf(data:str):
#     # dumb decode, use protoc, try to write it with python code, but ... QAQ
#     res = subprocess.run(['protoc','--decode_raw'],stdout=subprocess.PIPE,input=data,encoding='latin')
#     if res.returncode != 0:
#         return False
#     return res.stdout


# def DecodeGrpc(data:str):
#     data = base64.b64decode(data.encode('latin')).decode('latin')
#     msgs = []
    
#     while data:
#         tag = data[0]
#         data = data[1:]
#         if tag == '\x00':
#             # data
#             data_len = data[:4]
#             data = data[4:]
#             frame_len = struct.unpack('>I',data_len.encode('latin'))[0]
#             frame_data = data[:frame_len]
#             data = data[frame_len:]
#             msg = DecodeProtobuf(frame_data)
#             if msg == False:
#                 return False
#             msgs.append(msg)
#         elif tag == '\x80':
#             # trailer
#             data_len = data[:4]
#             data = data[4:]
#             trailer_len = struct.unpack('>I',data_len.encode('latin'))[0]
#             trailer_data = data[:trailer_len]
#             data[trailer_len:]
#             msgs.append(trailer_data)

#     return msgs



if __name__ == '__main__':

    import sys

    if len(sys.argv) > 1:
        print("")
        parser = ProtobufParser(sys.argv[1])
        try:
            grpc = parser.parse_grpc()
            print("gRPC Msg:\n")
            for msg in grpc['msgs']:
                print(msg)
                print('\n')
            print("gRPC Trailer:\n")
            print(grpc['trailer'])

            try:
                print("gRPC Test Encode Back:\n")
                encoder = ProtobufEncoder(grpc)
                res = encoder.encode_grpc()
                print('\t',res)
                print('\t',res==sys.argv[1],'\n')
            except Exception as result:
                print("Encoder Error, Sorry About the Dumb Code QAQ, Reason:",result)
        except Exception as result:
            print("Parse Error, Sorry About the Dumb Code QAQ, Reason:",result)

    else:
        print("please give me some input")