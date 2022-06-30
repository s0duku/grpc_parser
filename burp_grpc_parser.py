
from burp import IBurpExtender
from burp import IMessageEditorTabFactory
from burp import IMessageEditorTab
from burp import IParameter
from java.io import PrintWriter
from java.lang import RuntimeException
import json
from grpc_parser.parser import ProtobufEncoder, ProtobufParser

# https://github.com/PortSwigger/example-custom-editor-tab/blob/master/python/CustomEditorTab.py


class GrpcParserTab(IMessageEditorTab):
    # the display in text edit is the decode data
    def __init__(self, extender, controller, editable):
        self._extender = extender
        self._editable = editable

        # create an instance of Burp's text editor, to display our deserialized data
        self._txtInput = extender._callbacks.createTextEditor()
        self._txtInput.setEditable(editable)

    def getTabCaption(self):
        return "gRPC Parser"

    def getUiComponent(self):
        return self._txtInput.getComponent()

    def isEnabled(self, content, isRequest):
        # enable this tab for requests containing a data parameter
        # isRequest and not self._extender._helpers.getRequestParameter(content, "data") is None
        info = self._extender._helpers.analyzeRequest(content)
        offset = info.getBodyOffset()
        data = self._extender._helpers.bytesToString(content[offset:])
        try:
            parser = ProtobufParser(data)
            parser.parse_grpc()
            return True
        except:
            return False

    def setMessage(self, content, isRequest):
        if content is None:
            self._txtInput.setText(None)
            self._txtInput.setEditable(False)
        else:
            # parameter = self._extender._helpers.getRequestParameter(content, "data")
            info = self._extender._helpers.analyzeRequest(content)
            offset = info.getBodyOffset()
            header = self._extender._helpers.bytesToString(content[:offset])
            data = self._extender._helpers.bytesToString(content[offset:])
            try:
                # parse the grpc
                parser = ProtobufParser(data)
                grpc = parser.parse_grpc()

                # show it at editor
                self._txtInput.setText(header+json.dumps(grpc,indent=1))
                self._txtInput.setEditable(self._editable)

            except:
                self._txtInput.setText("\nUnable To Parse gRPC Message, Wrong Format, Or My Plugin Has Bug QAQ\n\n"+data)
                self._txtInput.setEditable(False)

        self._currentMessage = content

    def getMessage(self):
        # This method is used to retrieve the currently displayed message, which
        # may have been modified by the user.

        # edit message should finish this function.
        # for now, not complete

        if self._txtInput.isTextModified():
            text = self._txtInput.getText()
            try:
                info = self._extender._helpers.analyzeRequest(text)
            except:
                return self._currentMessage
            offset = info.getBodyOffset()
            header = self._extender._helpers.bytesToString(text[:offset])
            data = self._extender._helpers.bytesToString(text[offset:])
            # encode the data
            grpc = json.loads(data)
            try:
                encoder = ProtobufEncoder(grpc)
                return self._extender._helpers.stringToBytes(header+encoder.encode_grpc())
            except:
                return self._currentMessage
        else:
            return self._currentMessage

    def isModified(self):
        return self._txtInput.isTextModified()


    def getSelectedData(self):
        return self._txtInput.getSelectedText()

class BurpExtender(IBurpExtender,IMessageEditorTabFactory):

    def registerExtenderCallbacks(self, callbacks):
        # set extension name
        callbacks.setExtensionName("gRpc parser extension")

        # output and error streams
        
        stdout = PrintWriter(callbacks.getStdout(), True)
        self._stdout = stdout
        stderr = PrintWriter(callbacks.getStderr(), True)
        self._stderr = stderr

        stdout.println("\ngRPC Parser\n")
        stdout.println("\thttps://github.com/s0duku/grpc_parser.git\n")
        stdout.println("\tView/Modify gRPC Message Like Json Value.")
        stdout.println("\tDecode Result May Not Be Accurate, Because We Did Not Have The '.proto' File.")

        # keep a reference to our callbacks object
        self._callbacks = callbacks

        # obtain an extension helpers object
        self._helpers = callbacks.getHelpers()

        # register ourselves as a message editor tab factory
        callbacks.registerMessageEditorTabFactory(self)

        # throw an exception that will appear in our error stream
        # raise RuntimeException("Hello exception")

    def createNewInstance(self, controller, editable):
        return GrpcParserTab(self, controller, editable)