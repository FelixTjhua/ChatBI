from apps.template.template import get_base_template


def get_direct_answer_template():
    template = get_base_template()
    return template['template']['direct_answer']
