import jinja2
import yaml


class GeneratorHTMLVersionStatus:
    html_file_name = ""

    def create_template_for_mainpage(self):
        template_str = """<!DOCTYPE html>
<html>
<head>
<title>Openstack Version status</title>
</head>
<body>
<h1>Releases:</h1>
{% for release in packages_versions_data %}
<a href="{{ release }}.html" title="Link to {{ release }} release">
    <h2>{{ release }}</h2>
</a>
{% endfor %}
</body>
</html>"""
        with open("template_mainpage.j2", 'w') as f:
            f.write(template_str)
        return "template_mainpage.j2"

    def create_template_for_subpage(self):
        template_str = """<!DOCTYPE html>
<html>
<head>
<title>{{ release }}</title>
<style type="text/css">
.tg  {border-collapse:collapse;border-spacing:0;}
.tg td{border-color:black;border-style:solid;border-width:1px;font-family:Arial, sans-serif;font-size:14px;
  overflow:hidden;padding:10px 5px;word-break:normal;}
.tg th{border-color:black;border-style:solid;border-width:1px;font-family:Arial, sans-serif;font-size:14px;
  font-weight:normal;overflow:hidden;padding:10px 5px;word-break:normal;}
.tg .tg-1mfep{background-color:#C39BD3;border-color:inherit;font-weight:bold;text-align:center;vertical-align:middle}
.tg .tg-1mfer{background-color:#F1948A;border-color:inherit;font-weight:bold;text-align:center;vertical-align:middle}
.tg .tg-1mfeg{background-color:#7DCEA0;border-color:inherit;font-weight:bold;text-align:center;vertical-align:middle}
.tg .tg-1mfeo{background-color:#F0B27A;border-color:inherit;font-weight:bold;text-align:center;vertical-align:middle}
.tg .tg-lboi{border-color:inherit;text-align:left;vertical-align:middle}
.tg .tg-9wq8{border-color:inherit;text-align:center;vertical-align:middle}
.tg .tg-f4mc{background-color:#CCD1D1;border-color:inherit;text-align:center;font-weight:bold;vertical-align:middle}
</style>
</head>
<body>
<h2>{{ release }}</h2>
<table class="tg">
<thead>
  <tr>
    <th class="tg-f4mc">#</th>
    <th class="tg-f4mc">Upstream Source<br>Debian Source</th>
    <th class="tg-f4mc">Upstream<br>Version</th>
    <th class="tg-f4mc">Debian<br>Version</th>
    <th class="tg-f4mc">Status</th>
  </tr>
</thead>
<tbody>
{% for package in packages_versions_data %} 
    <tr>
        <td class="tg-9wq8">{{ loop.index }}.</td>
        <td class="tg-9wq8">{{ package }}</td>
        {% if "X" in packages_versions_data[package]['upstream_package_version'] %}
            <td class="tg-9wq8">{{ packages_versions_data[package]['upstream_package_version'] }}</td>
        {% else %}
            <td class="tg-9wq8"><a href="{{ packages_versions_data[package]['upstream_package_href'] }}">{{ packages_versions_data[package]['upstream_package_version'] }}</a></td>
        {% endif %}
        
        {% if "X" in packages_versions_data[package]['debian_package_version'] %}
            <td class="tg-9wq8">{{ packages_versions_data[package]['debian_package_version'] }}</td>
        {% else %}
            <td class="tg-9wq8"><a href="{{ packages_versions_data[package]['debian_package_href'] }}">{{ packages_versions_data[package]['debian_package_version'] }}</a></td>
        {% endif %}
        
        {% if "3" in packages_versions_data[package]['status'] %}
            <td class="tg-1mfer">missing in debian</td>
        {% endif %}
        
        {% if "2" in packages_versions_data[package]['status'] %}
            <td class="tg-1mfeg">up to date</td>
        {% endif %}
        
        {% if "1" in packages_versions_data[package]['status'] %}
            <td class="tg-1mfeo">out of date</td>
        {% endif %}
        
        {% if "4" in packages_versions_data[package]['status'] %}
            <td class="tg-1mfep">missing in upstream</td>
        {% endif %}
    </tr>
{% endfor %}
</tbody>
</table>
<br>
</body>
</html>"""
        with open("template_subpage.j2", 'w') as f:
            f.write(template_str)
        return "template_subpage.j2"

    def generate_mainpage(self, packages_versions_data):
        templateFilePath = jinja2.FileSystemLoader('./')
        jinjaEnv = jinja2.Environment(loader=templateFilePath)
        jTemplate = jinjaEnv.get_template(self.create_template_for_mainpage())
        output = jTemplate.render(packages_versions_data=packages_versions_data)
        print
        output
        with open(self.html_file_name, 'w') as f:
            f.write(output)
        for subpage in packages_versions_data:
            self.html_file_name = subpage + ".html"
            self.generate_subpage(subpage, packages_versions_data[subpage])
        return 0

    def generate_subpage(self, release, packages_versions_data):
        templateFilePath = jinja2.FileSystemLoader('./')
        jinjaEnv = jinja2.Environment(loader=templateFilePath)
        jTemplate = jinjaEnv.get_template(self.create_template_for_subpage())
        output = jTemplate.render(release=release, packages_versions_data=packages_versions_data)
        print
        output
        with open(self.html_file_name, 'w') as f:
            f.write(output)
        return 0
