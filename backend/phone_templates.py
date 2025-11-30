# phone_templates.py
# Basic region/national phone templates for Option C behavior.

PHONE_TEMPLATES = {
    "GB": {
        "regional": "+44 {area} {local}",
        "national": "+44 {area} {local}",
    },
    "IN": {
        "regional": "+91 {area} {local}",
        "national": "+91 {area} {local}",
    },
    "DE": {
        "regional": "+49 {area} {local}",
        "national": "+49 {area} {local}",
    },
    "US": {
        "regional": "+1 ({area}) {local}",
        "national": "+1 ({area}) {local}",
    },
    "IE": {
        "regional": "+353 {area} {local}",
        "national": "+353 {area} {local}",
    },
    "FR": {
        "regional": "+33 {area} {local}",
        "national": "+33 {area} {local}",
    },
    "ES": {
        "regional": "+34 {area} {local}",
        "national": "+34 {area} {local}",
    },
    "IT": {
        "regional": "+39 {area} {local}",
        "national": "+39 {area} {local}",
    },
    "NL": {
        "regional": "+31 {area} {local}",
        "national": "+31 {area} {local}",
    },
}
