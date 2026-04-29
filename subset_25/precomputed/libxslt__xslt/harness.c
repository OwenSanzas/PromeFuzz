// This fuzz driver is generated for library libxslt, aiming to fuzz the following functions:
// xsltFreeTransformContext at transform.c:722:1 in transform.h
// xsltProfileStylesheet at transform.c:6250:1 in transform.h
// xsltRunStylesheetUser at transform.c:6312:1 in transform.h
// xsltNewTransformContext at transform.c:565:1 in transform.h
// xsltRunStylesheet at transform.c:6373:1 in transform.h
// xsltApplyStylesheetUser at transform.c:6274:1 in transform.h
// xsltApplyStylesheet at transform.c:6231:1 in transform.h
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <libxml/parser.h>
#include <libxml/tree.h>
#include <libxml/xpath.h>
#include <libxslt/transform.h>
#include <libxslt/xsltutils.h>
#include <libxslt/xsltInternals.h>
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>

static xmlDocPtr createDummyXmlDoc() {
    xmlDocPtr doc = xmlNewDoc(BAD_CAST "1.0");
    xmlNodePtr root_node = xmlNewNode(NULL, BAD_CAST "root");
    xmlDocSetRootElement(doc, root_node);
    xmlNewChild(root_node, NULL, BAD_CAST "child1", BAD_CAST "content1");
    xmlNewChild(root_node, NULL, BAD_CAST "child2", BAD_CAST "content2");
    return doc;
}

static xsltStylesheetPtr createDummyStylesheet() {
    xmlDocPtr doc = createDummyXmlDoc();
    xsltStylesheetPtr style = xsltNewStylesheet();
    style->doc = doc;
    return style;
}

static void cleanup(xmlDocPtr doc, xsltStylesheetPtr style, xsltTransformContextPtr ctxt) {
    if (ctxt) xsltFreeTransformContext(ctxt);
    if (style) xsltFreeStylesheet(style);
    if (doc) xmlFreeDoc(doc);
}

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    xmlDocPtr doc = createDummyXmlDoc();
    xsltStylesheetPtr style = createDummyStylesheet();
    xsltTransformContextPtr ctxt = NULL;
    const char *params[16] = {NULL};
    FILE *dummyFile = fopen("./dummy_file", "w+");
    if (!dummyFile) {
        cleanup(doc, style, ctxt);
        return 0;
    }

    // Test xsltProfileStylesheet
    xmlDocPtr resultDoc1 = xsltProfileStylesheet(style, doc, params, dummyFile);
    if (resultDoc1) xmlFreeDoc(resultDoc1);

    // Test xsltRunStylesheetUser
    int runResult = xsltRunStylesheetUser(style, doc, params, NULL, NULL, NULL, dummyFile, NULL);

    // Test xsltNewTransformContext
    ctxt = xsltNewTransformContext(style, doc);

    // Test xsltRunStylesheet
    int runResult2 = xsltRunStylesheet(style, doc, params, NULL, NULL, NULL);

    // Test xsltApplyStylesheetUser
    xmlDocPtr resultDoc2 = xsltApplyStylesheetUser(style, doc, params, NULL, dummyFile, ctxt);
    if (resultDoc2) xmlFreeDoc(resultDoc2);

    // Test xsltApplyStylesheet
    xmlDocPtr resultDoc3 = xsltApplyStylesheet(style, doc, params);
    if (resultDoc3) xmlFreeDoc(resultDoc3);

    fclose(dummyFile);
    cleanup(doc, style, ctxt);
    return 0;
}