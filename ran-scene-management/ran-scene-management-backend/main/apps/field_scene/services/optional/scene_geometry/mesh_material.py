"""Copy-on-write material edits: each scene owns an immutable XML revision.

Legacy OSM material groups are normalized into individual extrusions once. The
original asset and scenes referencing it remain unchanged. Physics consumes the
new XML path through the existing geometry_source pipeline.
"""
import copy
import hashlib
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .mitsuba_shapes import list_shapes, resolve
from .osm_mesh_parts import part_bytes

EDIT_ROOT = Path('/app/scenes/scene_edits')


def _write(path, content):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        f.write(content)
        tmp = Path(f.name)
    tmp.replace(path)


def set_material(xml_path: str, shape_id: str, itu_id: str, scene_uuid: str) -> str:
    if not re.fullmatch(r'[A-Za-z0-9_-]+', scene_uuid) or not re.fullmatch(r'itu_[a-z0-9_]+', itu_id):
        raise ValueError('Invalid scene or material identifier')
    src = resolve(xml_path)
    if src is None:
        raise ValueError('找不到場景模型')
    shapes = list_shapes(str(src))
    selected = next((s for s in shapes if s['shape_id'] == shape_id and not s['too_large']), None)
    if selected is None:
        raise ValueError('找不到選取的建築／網格，請重新整理')
    directory = EDIT_ROOT / scene_uuid
    tree = ET.parse(src)
    root = tree.getroot()
    # Existing relative references must survive relocating the XML.
    for node in root.iter('string'):
        if node.get('name') == 'filename':
            value = node.get('value', '')
            if value and not Path(value).is_absolute():
                node.set('value', str((src.parent / value).resolve()))
    grouped = {}
    for s in shapes:
        grouped.setdefault(s['_shape_index'], []).append(s)
    parents = {child: parent for parent in root.iter() for child in parent}
    for i, original in enumerate(list(root.iter('shape'))):
        descriptors = grouped.get(i)
        if not descriptors:
            continue
        parent = parents[original]
        offset = list(parent).index(original)
        parent.remove(original)
        for j, descriptor in enumerate(descriptors):
            shape = copy.deepcopy(original)
            shape.set('id', descriptor['shape_id'])
            if '_vertex_range' in descriptor:
                content = part_bytes(descriptor['_path'], descriptor['_vertex_range'])
                mesh = directory / f"{hashlib.sha256(content).hexdigest()}.ply"
                _write(mesh, content)
                filename = next(s for s in shape.findall('string') if s.get('name') == 'filename')
                filename.set('value', str(mesh))
            if descriptor['shape_id'] == shape_id:
                ref = next(iter(shape.findall('ref')), None)
                if ref is None:
                    for bsdf in shape.findall('bsdf'):
                        shape.remove(bsdf)
                    ref = ET.SubElement(shape, 'ref')
                ref.set('id', itu_id)
            parent.insert(offset + j, shape)
    if not any(b.get('id') == itu_id for b in root.findall('bsdf')):
        from main.apps.render_osm_footprint.services.optional.osm_to_mitsuba import DISPLAY_RGB
        bsdf = ET.Element('bsdf', {'type': 'diffuse', 'id': itu_id})
        ET.SubElement(bsdf, 'rgb', {'name': 'reflectance', 'value': DISPLAY_RGB.get(itu_id, '0.5 0.5 0.5')})
        root.insert(0, bsdf)
    content = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    target = directory / f'{hashlib.sha256(content).hexdigest()}.xml'
    _write(target, content)
    return str(target)
