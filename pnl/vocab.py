"""One name per concept (DESIGN.md 10) and the picklists the workspace offers.

Stored values are never rewritten: older spellings are mapped when they're read
(normalise_*), and saved in the new form only when someone saves the project.
"""

STATUSES = ['Draft', 'Submitted', 'Won', 'Lost', 'On hold']
STAGES = ['Qualification', 'Discovery', 'Solutioning', 'Proposal', 'Commercial review', 'Negotiation', 'Closed']
PRIORITIES = ['Low', 'Medium', 'High', 'Critical']
DELIVERY_MODELS = ['Offshore', 'Onsite', 'Hybrid', 'Managed service']
BILLING_TYPES = ['Time and material', 'Fixed bid', 'Milestone based', 'Retainer']
CURRENCIES = ['USD', 'INR', 'EUR', 'GBP', 'AED', 'SGD']
LICENSE_TYPES = ['AI', 'Platform', 'Project management', 'Other']
INDUSTRIES = ['Aviation', 'Banking', 'Construction', 'Education', 'Energy', 'Financial services', 'FMCG', 'Government',
              'Healthcare', 'Hospitality', 'Insurance', 'Logistics', 'Manufacturing', 'Media', 'Oil and gas', 'Packaging',
              'Pharma', 'Real estate', 'Retail', 'Shipping', 'Technology', 'Telecom', 'Utilities', 'Other']
PROJECT_TYPES = ['Assessment', 'POC', 'MVP', 'Implementation', 'Migration', 'OTC', 'OTC+AMS', 'AMS', 'MRC',
                 'Managed service', 'Resource request', 'RPA', 'MSFT funded', 'Other']
COUNTRIES = ["Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bhutan", "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia", "Cameroon", "Canada", "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros", "Congo (Brazzaville)", "Congo (Kinshasa)", "Costa Rica", "Croatia", "Cuba", "Cyprus", "Czech Republic", "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti", "Honduras", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania", "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", "Palestine", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar", "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Solomon Islands", "Somalia", "South Africa", "South Korea", "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United States", "Uruguay", "Uzbekistan", "Vanuatu", "Vatican City", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe"]

_STATUS_MAP = {'on hold': 'On hold', 'active': 'Submitted', 'proposal': 'Submitted'}
_STAGE_MAP = {'commercial review': 'Commercial review', 'closed won': 'Closed', 'closed lost': 'Closed'}
_DELIVERY_MAP = {'managed service': 'Managed service'}
_BILLING_MAP = {'time & material': 'Time and material', 'fixed bid': 'Fixed bid', 'milestone based': 'Milestone based'}
_PROJECT_TYPE_MAP = {'resource request': 'Resource request', 'msft funded': 'MSFT funded'}
# Old license rows only had a label; map it to the new license type.
_LICENSE_LABEL_TYPE = {'ai subscriptions': 'AI', 'other project management licenses': 'Project management'}


def _norm(value, allowed, mapping):
    v = str(value or '').strip()
    if not v:
        return v
    if v in allowed:
        return v
    low = v.lower()
    if low in mapping:
        return mapping[low]
    for a in allowed:
        if a.lower() == low:
            return a
    return v        # unknown values are kept as they are


def normalise_status(v):
    return _norm(v, STATUSES, _STATUS_MAP) or 'Draft'


def normalise_stage(v):
    return _norm(v, STAGES, _STAGE_MAP)


def normalise_project(project: dict) -> dict:
    """A copy of a stored `project` dict with values in the current vocabulary."""
    p = dict(project or {})
    p['status'] = normalise_status(p.get('status'))
    p['stage'] = normalise_stage(p.get('stage'))
    p['delivery_model'] = _norm(p.get('delivery_model'), DELIVERY_MODELS, _DELIVERY_MAP)
    p['billing_type'] = _norm(p.get('billing_type'), BILLING_TYPES, _BILLING_MAP)
    p['project_type'] = _norm(p.get('project_type'), PROJECT_TYPES, _PROJECT_TYPE_MAP)
    return p


def license_type(item: dict) -> str:
    t = (item or {}).get('license_type')
    if t in LICENSE_TYPES:
        return t
    return _LICENSE_LABEL_TYPE.get(str((item or {}).get('label', '')).strip().lower(), 'Other')
