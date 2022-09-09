from schema import Schema

preset_structure = Schema(
    [
        {
            'name': str,
            'type': str,
            'text': str,
            'dropdown_options': [

            ]
        }
    ]
)

overall_structure = Schema(
    {
        'presets': preset_structure,
        'role_categories': list,
        'messages': list
    }
)

    