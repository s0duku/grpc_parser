
# gRPC parser

python tool for decode the gRPC message body

* almost not possible for parsing gRPC message correctly without '.proto' file
* even 'protoc' can not do that
* this tool make sure the parsing result matches protoc's result
* this extension will add a new tab at burp, if the body's data can't be parsed tab will not display

## references

* https://developers.google.com/protocol-buffers/docs/encoding#optional


## usage

* you can simply run or import the library to your python code, or just use it as the BurpSuite extension

```
python3 grpc_parser/parser.py YOU_GRPC_MESSAGE

```


