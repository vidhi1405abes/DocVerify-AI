"""Supported document types: what each one must contain and how to recognise it."""

DOCUMENT_TYPES = {
    "marksheet10": {
        "name": "10th Marksheet",
        "description": "Class 10 board examination marks statement",
        "formats": [".pdf", ".jpg", ".jpeg", ".png", ".webp"],
        "required": ["name", "rollNumber", "dateOfBirth", "subjects", "result"],
        "identifiers": ["rollNumber", "serialNumber"],
        "seeds": [
            "केन्द्रीय माध्यमिक शिक्षा बोर्ड अंक विवरणिका सह प्रमाण पत्र माध्यमिक विद्यालय परीक्षा अनुक्रमांक माता का नाम पिता का नाम जन्म तिथि विद्यालय विषय अंक योग परिणाम उत्तीर्ण हाई स्कूल परीक्षा",
            "central board of secondary education marks statement cum certificate secondary school "
            "examination this is to certify that roll no mother's name father's guardian's name date of "
            "birth school has achieved scholastic achievements sub code subject theory practical total "
            "total in words positional grade english hindi mathematics science social science result pass",
            "board of secondary education class x high school examination marksheet roll number name of "
            "candidate date of birth subjects marks obtained maximum marks grade total result passed",
        ],
    },
    "marksheet12": {
        "name": "12th Marksheet",
        "description": "Class 12 board examination marks statement",
        "formats": [".pdf", ".jpg", ".jpeg", ".png", ".webp"],
        "required": ["name", "rollNumber", "subjects", "result"],
        "identifiers": ["rollNumber", "serialNumber"],
        "seeds": [
            "केन्द्रीय माध्यमिक शिक्षा बोर्ड अंक विवरणिका सह प्रमाण पत्र वरिष्ठ विद्यालय प्रमाणपत्र परीक्षा उच्चतर माध्यमिक इण्टरमीडिएट परीक्षा अनुक्रमांक भौतिकी रसायन विज्ञान गणित परिणाम उत्तीर्ण",
            "central board of secondary education marks statement cum certificate senior school "
            "certificate examination this is to certify that roll no mother's name father's name school "
            "sub code subject theory practical total in words grade english core physics chemistry "
            "mathematics biology physical education general studies work experience result pass",
            "board of higher secondary education class xii intermediate examination marksheet roll "
            "number name subjects physics chemistry mathematics marks obtained grade total result",
        ],
    },
    "jeeResult": {
        "name": "JEE Result",
        "description": "Joint Entrance Examination (Main) score card",
        "formats": [".pdf"],
        "required": ["name", "applicationNumber", "totalPercentile"],
        "identifiers": ["applicationNumber", "rollNumber"],
        "seeds": [
            "राष्ट्रीय परीक्षा एजेंसी संयुक्त प्रवेश परीक्षा मुख्य स्कोर कार्ड आवेदन संख्या अभ्यर्थी का नाम पर्सेंटाइल",
            "national testing agency joint entrance examination jee main score card application number "
            "candidate's name mother's name father's name category person with disability date of birth "
            "gender state of eligibility nationality nta score percentile mathematics physics chemistry "
            "total nta score result status all india rank",
        ],
    },
    "tc": {
        "name": "Transfer Certificate",
        "description": "School leaving / transfer certificate",
        "formats": [".pdf", ".jpg", ".jpeg", ".png", ".webp"],
        "required": ["name", "fatherName", "dateOfBirth", "leavingDate"],
        "identifiers": ["admissionNumber", "certificateNumber"],
        "seeds": [
            "स्थानांतरण प्रमाण पत्र विद्यालय परित्याग प्रमाण पत्र प्रवेश संख्या छात्र का नाम पिता का नाम जन्म तिथि प्रवेश की तिथि विद्यालय छोड़ने की तिथि आचरण प्रधानाचार्य",
            "transfer certificate school leaving certificate admission no name of pupil father's guardian's "
            "name mother's name nationality date of birth in figures in words date of admission class "
            "date of leaving the school reason for leaving conduct and character whether qualified for "
            "promotion principal signature date of issue",
        ],
    },
    "domicile": {
        "name": "Domicile Certificate",
        "description": "State domicile / residence certificate",
        "formats": [".pdf", ".jpg", ".jpeg", ".png", ".webp"],
        # An application form carries an application number and date instead of the issued ones.
        "required": ["name", "fatherName", "state", ("issueDate", "applicationDate"),
                     ("certificateNumber", "applicationNumber")],
        "identifiers": ["certificateNumber", "applicationNumber"],
        "seeds": [
            "निवास प्रमाण पत्र स्थायी निवास प्रमाण पत्र आवासीय प्रमाण पत्र प्रमाणित किया जाता है कि पिता का नाम ग्राम थाना प्रखंड अंचल जिला राज्य का निवासी अंचल अधिकारी आवेदन पत्र संख्या",
            "domicile certificate government of state revenue department certificate no this is to certify "
            "that son of daughter of resident of village tehsil district state has been residing "
            "permanently is a domicile of the state issuing authority tehsildar sub divisional magistrate "
            "date of issue place",
        ],
    },
    "aadhaar": {
        "name": "Aadhaar Card",
        "description": "UIDAI Aadhaar identity card or e-Aadhaar letter",
        "formats": [".pdf", ".jpg", ".jpeg", ".png", ".webp"],
        "required": ["name", "dateOfBirth", "gender", "aadhaarNumber"],
        "identifiers": ["aadhaarNumber"],
        "seeds": [
            "भारत सरकार भारतीय विशिष्ट पहचान प्राधिकरण आधार मेरा आधार मेरी पहचान जन्म तिथि पुरुष महिला पता",
            "government of india unique identification authority of india aadhaar your aadhaar no "
            "enrolment no dob date of birth male female address s/o c/o vid aadhaar is proof of identity "
            "not of citizenship mera aadhaar meri pehchaan verify identity using secure qr code",
        ],
    },
}

FIELD_LABELS = {
    "name": "Name",
    "rollNumber": "Roll number",
    "serialNumber": "Serial number",
    "applicationNumber": "Application number",
    "admissionNumber": "Admission number",
    "certificateNumber": "Certificate number",
    "aadhaarNumber": "Aadhaar number",
    "motherName": "Mother's name",
    "fatherName": "Father's / guardian's name",
    "dateOfBirth": "Date of birth",
    "dateOfBirthInWords": "Date of birth (in words)",
    "gender": "Gender",
    "school": "School",
    "board": "Issuing board / authority",
    "examination": "Examination",
    "examYear": "Examination year",
    "subjects": "Subjects and marks",
    "result": "Result",
    "issueDate": "Date of issue",
    "applicationDate": "Date of application",
    "admissionDate": "Date of admission",
    "leavingDate": "Date of leaving",
    "class": "Class",
    "state": "State",
    "district": "District",
    "address": "Address",
    "totalPercentile": "Total percentile / NTA score",
    "rank": "Rank",
    "cgpa": "CGPA",
    "percentage": "Percentage",
    "grandTotal": "Grand total",
}


def required_label(requirement):
    """A required field, or a tuple of alternatives of which any one is enough."""
    if isinstance(requirement, tuple):
        return " or ".join(FIELD_LABELS[field] for field in requirement)
    return FIELD_LABELS[requirement]


def required_present(requirement, fields):
    options = requirement if isinstance(requirement, tuple) else (requirement,)
    return any(fields.get(field) for field in options)


def public_types():
    return [
        {
            "id": type_id,
            "name": spec["name"],
            "description": spec["description"],
            "formats": spec["formats"],
            "requiredFields": [required_label(field) for field in spec["required"]],
        }
        for type_id, spec in DOCUMENT_TYPES.items()
    ]
