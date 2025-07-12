import argparse,re,os
from collections import defaultdict

ALLOWED_GATES = {"AND", "NAND", "OR", "XOR", "NXOR", "NOT"}
GATE_STYLE = 'verticalLabelPosition=bottom;shadow=0;dashed=0;align=center;html=1;verticalAlign=top;shape=mxgraph.electrical.logic_gates.logic_gate;'
WIRE_STYLE_025 = 'edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;entryX=0;entryY=0.25;entryDx=0;entryDy=0;entryPerimeter=0;'
WIRE_STYLE_075 = 'edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;entryX=0;entryY=0.75;entryDx=0;entryDy=0;entryPerimeter=0;'
GATE_SETTING = 'vertex="1" parent="1"'
SPACEX2 = "  "
SPACEX4 = "    "

def get_max_gate_level(gates):
    if not gates:
        return 0
    return max(gate["level"] for gate in gates)

def get_gate_style(logic_type):
    base = GATE_STYLE
    if logic_type == "AND":
        return f"{base}operation=and;"
    if logic_type == "NAND":
        return f"{base}operation=and;negating=1;negSize=0.15;"
    if logic_type == "OR":
        return f"{base}operation=or;"
    if logic_type == "XOR":
        return f"{base}operation=xor;"
    if logic_type == "NXOR":
        return f"{base}operation=xor;negating=1;negSize=0.15;"
    if logic_type == "NOT":
        return f"{base}operation=inverter_2;negating=1;negSize=0.15;"
    return base

def parse_verilog_netlist(verilog_str):
    inputs = []
    outputs = []
    wires = []
    gates = []
    gate_count = defaultdict(int)
    net_to_gate_output = dict()
    gate_inputs_map = dict()

    for line in verilog_str.splitlines():
        line = line.strip()
        if not line or line.startswith('//') or line.startswith("module") or line.startswith("endmodule"):
            continue
        if line.startswith("input"):
            inputs += re.findall(r'\w+', line)[1:]
        elif line.startswith("output"):
            outputs += re.findall(r'\w+', line)[1:]
        elif line.startswith("wire"):
            wires += re.findall(r'\w+', line)[1:]
        else:
            m = re.match(r'(\w+)\s+(\w+)\s*\(([^)]+)\);', line)
            if m:
                gate_type, gate_name, ports = m.groups()
                gate_type_upper = gate_type.upper()
                if gate_type_upper in ALLOWED_GATES:
                    port_list = [p.strip() for p in ports.split(',')]
                    output_net = port_list[0]
                    input_nets = port_list[1:]
                    gates.append({
                        "type": gate_type_upper,
                        "name": gate_name,
                        "output": output_net,
                        "inputs": input_nets
                    })
                    gate_inputs_map[gate_name] = input_nets
                    net_to_gate_output[output_net] = gate_name
                    gate_count[gate_type_upper] += 1

    gate_level = dict()
    unresolved = set(g["name"] for g in gates)
    while unresolved:
        progress = False
        for g in list(unresolved):
            input_levels = []
            inputs_ready = True
            for net in gate_inputs_map[g]:
                if net in inputs:
                    input_levels.append(0)
                elif net in net_to_gate_output:
                    src_gate = net_to_gate_output[net]
                    if src_gate in gate_level:
                        input_levels.append(gate_level[src_gate])
                    else:
                        inputs_ready = False
                        break
                else:
                    input_levels.append(0)

            if inputs_ready:
                gate_level[g] = max(input_levels) + 1
                unresolved.remove(g)
                progress = True

        if not progress:
            raise ValueError("Cyclic dependency or unresolved nets detected!")

    for g in gates:
        g["level"] = gate_level[g["name"]]

    return {
        "inputs": inputs,
        "outputs": outputs,
        "wires": wires,
        "gate_counts": dict(gate_count),
        "gates": gates
    }

def write_to_xml(name, result):
    component_dict = {}
    inputs = result["inputs"]
    outputs = result["outputs"]
    gates = result["gates"]
    max_level = get_max_gate_level(gates)
    max_width = max_level * 70
    id_counter = 0
    xml = f'<mxfile>{SPACEX2}\n<diagram name="{name}">\n{SPACEX4}<mxGraphModel>\n{SPACEX2}{SPACEX4}<root>\n{SPACEX4}{SPACEX4}<mxCell id="0" />\n{SPACEX4}{SPACEX4}<mxCell id="1" parent="0" />\n'

    # Input nodes
    for input_name in inputs:
        cell_id = f"0_{id_counter}"
        y_cor = id_counter * 50
        xml += f'{SPACEX4}{SPACEX4}{SPACEX2}<mxCell id="{cell_id}" value="{input_name}" style="text;html=1;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;" vertex="1" parent="1">\n'
        xml += f'{SPACEX4}{SPACEX4}{SPACEX4}<mxGeometry x="0" y="{y_cor}" width="30" height="30" as="geometry" />\n{SPACEX4}{SPACEX4}{SPACEX2}</mxCell>\n'
        component_dict[input_name] = cell_id
        id_counter += 1

    xml += "\n\n"

    # Output nodes
    for j, output_name in enumerate(outputs):
        cell_id = f"0_{id_counter}"
        y_cor = j * 50
        xml += f'{SPACEX4}{SPACEX4}{SPACEX2}<mxCell id="{cell_id}" value="{output_name}" style="text;html=1;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;" vertex="1" parent="1">\n'
        xml += f'{SPACEX4}{SPACEX4}{SPACEX4}<mxGeometry x="{max_width}" y="{y_cor}" width="30" height="30" as="geometry" />\n{SPACEX4}{SPACEX4}{SPACEX2}</mxCell>\n'
        component_dict[output_name] = cell_id
        id_counter += 1

    xml += "\n\n"

    level_record = {level + 1: [] for level in range(max_level)}
    pin_record = {}

    # Gate nodes
    for gate in gates:
        gate_id = f"0_{id_counter}"
        gate_name = gate['name']
        gate_level = gate['level']
        logic = gate['type']
        style = get_gate_style(logic)

        x_cor = gate_level * 50
        y_cors = level_record[gate_level]
        if y_cors:
            y_cor = y_cors[-1] + 70
            y_cors.append(y_cor)
        else:
            y_cor = 5
            y_cors.append(y_cor)

        xml += f'{SPACEX4}{SPACEX4}{SPACEX2}<mxCell id="{gate_id}" value="{gate_name}" style="{style}" {GATE_SETTING}>\n'
        xml += f'{SPACEX4}{SPACEX4}{SPACEX4}<mxGeometry x="{x_cor}" y="{y_cor}" width="30" height="30" as="geometry" />\n{SPACEX4}{SPACEX4}{SPACEX2}</mxCell>\n'

        component_dict[gate_name] = gate_id
        pin_record[gate_name] = False
        id_counter += 1

    xml += "\n\n"

    # Wire connections
    for gate in gates:
        gate_name = gate['name']
        in_wires = gate['inputs']
        out_wire = gate['output']
        component_dict[out_wire] = component_dict[gate_name]

        for j, net in enumerate(in_wires):
            wire_id = f"0_{gate_name}_{j}_wire"
            style = WIRE_STYLE_025 if not pin_record[gate_name] else WIRE_STYLE_075
            pin_record[gate_name] = True
            xml += f'{SPACEX4}{SPACEX4}{SPACEX2}<mxCell id="{wire_id}" style="{style}" edge="1" parent="1" source="{component_dict[net]}" target="{component_dict[gate_name]}">\n'
            xml += f'{SPACEX4}{SPACEX4}{SPACEX4}<mxGeometry relative="1" as="geometry" />\n{SPACEX4}{SPACEX4}{SPACEX2}</mxCell>\n'

    # Finalize XML
    xml += '</root>\n</mxGraphModel>\n</diagram>\n</mxfile>'

    with open(f"{name}.xml", "w") as f:
        f.writelines(xml)

    print(f"(V) XML saved to: {name}.xml")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Generate circuit XML diagram from .vg netlist file(s)")
    parser.add_argument("vg_files", nargs="+", help="Path(s) to .vg netlist file(s)")

    args = parser.parse_args()

    for vg_file in args.vg_files:
        if not os.path.isfile(vg_file):
            print(f"(X) File not found: {vg_file}")
            continue

        try:
            with open(vg_file, "r") as f:
                content = f.read()
            result = parse_verilog_netlist(content)

            # Get base name (remove path and .vg extension)
            base_name = os.path.splitext(os.path.basename(vg_file))[0]
            write_to_xml(base_name, result)
        except Exception as e:
            print(f"(!) Error processing {vg_file}: {e}")

