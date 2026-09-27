"""Two Figure 1 examples and one explicitly synthetic branch test."""

from __future__ import annotations

import json


DIRECT_LOG = """060413 160702 Lost connection to JobTracker [kry1040/72.30.116.100:50020]. Retrying...
java.io.IOException: No valid local directories in property: mapred.local.dir
at org.apache.hadoop.conf.Configuration.getFile(Configuration.java:282)
at org.apache.hadoop.mapred.JobConf.getLocalFile(JobConf.java:127)"""
DIRECT_CONFIG = json.dumps(
    {
        "mapred.local.dir": {
            "value": "<missing>",
            "description": "Local directories used by the task tracker.",
        },
        "mapreduce.job.retries": {"value": "3", "description": "Job retry count."},
    },
    ensure_ascii=False,
    indent=2,
)

INDIRECT_LOG = """java.lang.NullPointerException
at org.apache.hadoop.security.LdapGroupsMapping.goUpGroupHierarchy(LdapGroupsMapping.java:612)
at org.apache.hadoop.security.LdapGroupsMapping.lookupGroup(LdapGroupsMapping.java:489)
at org.apache.hadoop.security.LdapGroupsMapping.doGetGroups(LdapGroupsMapping.java:552)
at org.apache.hadoop.security.LdapGroupsMapping.getGroups(LdapGroupsMapping.java:365)"""
INDIRECT_CONFIG = json.dumps(
    {
        "hadoop.security.group.mapping.ldap.search.group.hierarchy.levels": {
            "value": "<missing>",
            "description": "Number of LDAP group hierarchy levels to search.",
        },
        "mapred.local.dir": {"value": "/tmp/hadoop", "description": "Local task directories."},
    },
    ensure_ascii=False,
    indent=2,
)

CASES = {
    "direct": {
        "title": "论文图 1 · mapred.local.dir（直接症状）",
        "log": DIRECT_LOG,
        "config": DIRECT_CONFIG,
        "normal_templates": [
            "Lost connection to JobTracker [<*>]. Retrying...",
            "TaskTracker started successfully",
        ],
        "expected_property": "mapred.local.dir",
        "expected_flow": "fast-flow",
        "test_only": False,
    },
    "indirect": {
        "title": "论文图 1 · LdapGroupsMapping（间接症状）",
        "log": INDIRECT_LOG,
        "config": INDIRECT_CONFIG,
        "normal_templates": [
            "LDAP group lookup completed",
            "TaskTracker started successfully",
        ],
        "expected_property": "hadoop.security.group.mapping.ldap.search.group.hierarchy.levels",
        "expected_flow": "direct-flow",
        "test_only": False,
    },
    "complete_test": {
        "title": "测试案例 · 强制验证失败（complete-flow）",
        "log": DIRECT_LOG,
        "config": DIRECT_CONFIG,
        "normal_templates": [
            "Lost connection to JobTracker [<*>]. Retrying...",
            "TaskTracker started successfully",
        ],
        "expected_property": "mapred.local.dir",
        "expected_flow": "complete-flow",
        "test_only": True,
    },
}
