// This fuzz driver is generated for library libxslt, aiming to fuzz the following functions:
// xsltRunStylesheetUser at transform.c:6312:1 in transform.h
// xsltSetXIncludeDefault at transform.c:454:1 in transform.h
// xsltCopyTextString at transform.c:882:1 in transform.h
// xsltLocalVariablePush at transform.c:2237:1 in transform.h
// xsltLocalVariablePop at transform.c:179:1 in transform.h
// xsltGetXIncludeDefault at transform.c:466:1 in transform.h
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <libxslt/transform.h>
#include <libxml/parser.h>
#include <libxml/tree.h>
#include <libxml/xmlIO.h>
#include <libxml/xpathInternals.h>
#include <stdio.h>
#include <stdint.h>

static xsltStylesheetPtr createDummyStylesheet() {
    xsltStylesheetPtr style = (xsltStylesheetPtr) xmlMalloc(sizeof(xsltStylesheet));
    if (style) {
        memset(style, 0, sizeof(xsltStylesheet));
    }
    return style;
}

static xmlDocPtr createDummyXmlDoc() {
    xmlDocPtr doc = xmlNewDoc(BAD_CAST "1.0");
    if (doc) {
        xmlNodePtr root = xmlNewNode(NULL, BAD_CAST "root");
        xmlDocSetRootElement(doc, root);
    }
    return doc;
}

static xsltTransformContextPtr createDummyTransformContext(xsltStylesheetPtr style) {
    xsltTransformContextPtr ctxt = (xsltTransformContextPtr) xmlMalloc(sizeof(xsltTransformContext));
    if (ctxt) {
        memset(ctxt, 0, sizeof(xsltTransformContext));
        ctxt->style = style;
    }
    return ctxt;
}

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    if (Size < 1) return 0;

    xsltStylesheetPtr style = createDummyStylesheet();
    xmlDocPtr doc = createDummyXmlDoc();
    xsltTransformContextPtr ctxt = createDummyTransformContext(style);

    // Prepare parameters
    const char *params[] = { NULL };

    // Create a dummy output buffer
    xmlOutputBufferPtr outputBuffer = xmlAllocOutputBuffer(NULL);

    // Create a dummy SAX handler
    xmlSAXHandlerPtr saxHandler = (xmlSAXHandlerPtr) xmlMalloc(sizeof(xmlSAXHandler));
    if (saxHandler) {
        memset(saxHandler, 0, sizeof(xmlSAXHandler));
    }

    // Dummy file for profile
    FILE *profile = fopen("./dummy_file", "w");

    // Call xsltRunStylesheetUser
    xsltRunStylesheetUser(style, doc, params, NULL, saxHandler, outputBuffer, profile, ctxt);

    // Call xsltSetXIncludeDefault
    xsltSetXIncludeDefault(Data[0] % 2);

    // Call xsltCopyTextString
    xmlNodePtr targetNode = xmlNewNode(NULL, BAD_CAST "target");
    xsltCopyTextString(ctxt, targetNode, BAD_CAST "test string", Data[0] % 2);

    // Call xsltLocalVariablePush and xsltLocalVariablePop
    xsltStackElemPtr var = (xsltStackElemPtr) xmlMalloc(sizeof(xsltStackElem));
    if (var) {
        memset(var, 0, sizeof(xsltStackElem));
        xsltLocalVariablePush(ctxt, var, 0);
        xsltLocalVariablePop(ctxt, 0, 0);
    }

    // Call xsltGetXIncludeDefault
    xsltGetXIncludeDefault();

    // Cleanup
    if (profile) fclose(profile);
    if (saxHandler) xmlFree(saxHandler);
    if (outputBuffer) xmlOutputBufferClose(outputBuffer);
    if (targetNode) xmlFreeNode(targetNode);
    if (var) xmlFree(var);
    if (ctxt) xmlFree(ctxt);
    if (doc) xmlFreeDoc(doc);
    if (style) xmlFree(style);

    return 0;
}