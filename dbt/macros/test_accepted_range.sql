{% test accepted_range(model, column_name, min_value=none, max_value=none) %}
select *
from {{ model }}
where
    {% if min_value is not none %}
    {{ column_name }} < {{ min_value }}
    {% else %}
    false
    {% endif %}
    {% if max_value is not none %}
    or {{ column_name }} > {{ max_value }}
    {% endif %}
{% endtest %}

