"""Supported document types: what each one must contain and how to recognise it."""

DOCUMENT_TYPES = {
    "marksheet10": {
        "name": "10th Marksheet",
        "description": "Class 10 board examination marks statement",
        "formats": [".pdf", ".jpg", ".jpeg", ".png"],
        "required": ["name", "rollNumber", "dateOfBirth", "subjects", "result"],
        "identifiers": ["rollNumber", "serialNumber"],
        "seeds": [
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
        "formats": [".pdf", ".jpg", ".jpeg", ".png"],
        "required": ["name", "rollNumber", "subjects", "result"],
        "identifiers": ["rollNumber", "serialNumber"],
        "seeds": [
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
            "national testing agency joint entrance examination jee main score card application number "
            "candidate's name mother's name father's name category person with disability date of birth "
            "gender state of eligibility nationality nta score percentile mathematics physics chemistry "
            "total nta score result status all india rank",
        ],
    },
    "tc": {
        "name": "Transfer Certificate",
        "description": "School leaving / transfer certificate",
        "formats": [".pdf", ".jpg", ".jpeg", ".png"],
        "required": ["name", "fatherName", "dateOfBirth", "leavingDate"],
        "identifiers": ["admissionNumber", "certificateNumber"],
        "seeds": [
            "transfer certificate school leaving certificate admission no name of pupil father's guardian's "
            "name mother's name nationality date of birth in figures in words date of admission class "
            "date of leaving the school reason for leaving conduct and character whether qualified for "
            "promotion principal signature date of issue",
        ],
    },
    "domicile": {
        "name": "Domicile Certificate",
        "description": "State domicile / residence certificate",
        "formats": [".pdf", ".jpg", ".jpeg", ".png"],
        "required": ["name", "fatherName", "state", "issueDate", "certificateNumber"],
        "identifiers": ["certificateNumber"],
        "seeds": [
            "domicile certificate government of state revenue department certificate no this is to certify "
            "that son of daughter of resident of village tehsil district state has been residing "
            "permanently is a domicile of the state issuing authority tehsildar sub divisional magistrate "
            "date of issue place",
        ],
    },
    "aadhaar": {
        "name": "Aadhaar Card",
        "description": "UIDAI Aadhaar identity card or e-Aadhaar letter",
        "formats": [".pdf", ".jpg", ".jpeg", ".png"],
        "required": ["name", "dateOfBirth", "gender", "aadhaarNumber"],
        "identifiers": ["aadhaarNumber"],
        "seeds": [
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


def public_types():
    return [
        {
            "id": type_id,
            "name": spec["name"],
            "description": spec["description"],
            "formats": spec["formats"],
            "requiredFields": [FIELD_LABELS[field] for field in spec["required"]],
        }
        for type_id, spec in DOCUMENT_TYPES.items()
    ]
