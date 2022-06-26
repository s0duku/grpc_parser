
# gRPC parser

python tool for decode the gRPC message body

* almost not possible for parsing gRPC message correctly with out '.proto' file
* even 'protoc' can not do that
* this tool make sure the parsing result matches protoc's result
* this extension will add a new tab at burp, if the body's data can't be parsed tab will not display

## references

* https://developers.google.com/protocol-buffers/docs/encoding#optional


## usage

* you can simply run or import the library to your python code, or just use it as the Burp extension

```
python3 grpc_parser/parser.py YOU_GRPC_MESSAGE

```

![0](https://github.com/s0duku/grpc_parser/blob/dde0e58c84949b5f0b8dd6fa9c76e0f768029d81/examples/0.png)

![1](https://github.com/s0duku/grpc_parser/blob/dde0e58c84949b5f0b8dd6fa9c76e0f768029d81/examples/1.png)
