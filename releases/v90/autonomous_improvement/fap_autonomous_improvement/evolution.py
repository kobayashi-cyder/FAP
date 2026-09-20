from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from fap_generic_skill import (
    BindingRegistry,
    SkillEdge,
    SkillNode,
    SkillSpec,
)


@dataclass(frozen=True)
class EvolvedSkill:
    parent_skill_id: str
    candidate: SkillSpec
    mutation: str


class SkillEvolution:
    """Bounded structural mutation of V86 declarative binding DAGs.

    Variants are candidates only. They receive no execution/promotion rights
    until they pass the normal V86 Skill Factory verifier.
    """

    def __init__(self, bindings: BindingRegistry):
        self.bindings = bindings

    def mutate(
        self,
        parent: SkillSpec,
        *,
        max_variants: int = 8,
    ) -> list[EvolvedSkill]:
        limit = max(1, min(16, int(max_variants)))
        eligible = [
            binding
            for binding in self.bindings.bindings.values()
            if self.bindings.is_eligible(binding.binding_id)
        ]
        eligible.sort(key=lambda x: x.binding_id)
        variants: list[EvolvedSkill] = []
        seen: set[str] = set()

        def add(
            nodes: Sequence[SkillNode],
            edges: Sequence[SkillEdge],
            output_node: str,
            mutation: str,
        ) -> None:
            if len(variants) >= limit:
                return
            try:
                spec = SkillSpec.create(
                    name=f"{parent.name}_{mutation}",
                    ability=parent.ability,
                    tags=parent.tags,
                    nodes=tuple(nodes),
                    edges=tuple(edges),
                    output_node=output_node,
                )
            except Exception:
                return
            if spec.skill_id == parent.skill_id or spec.skill_id in seen:
                return
            seen.add(spec.skill_id)
            variants.append(EvolvedSkill(parent.skill_id, spec, mutation))

        used = {node.binding_id for node in parent.nodes}
        node_list = list(parent.nodes)

        for index, node in enumerate(parent.nodes):
            current = self.bindings.get(node.binding_id)
            current_tags = {str(x).lower() for x in current.tags}
            for binding in eligible:
                if binding.binding_id in used:
                    continue
                if not current_tags.intersection(
                    {str(x).lower() for x in binding.tags}
                ):
                    continue
                replaced = list(node_list)
                replaced[index] = SkillNode(node.node_id, binding.binding_id)
                add(
                    replaced,
                    parent.edges,
                    parent.output_node,
                    f"replace_{index}_{binding.binding_id.replace('.', '_')}",
                )
                if len(variants) >= limit:
                    return variants

        for binding in eligible:
            if binding.binding_id in used:
                continue
            if not set(str(x).lower() for x in binding.tags).intersection(
                set(str(x).lower() for x in parent.tags)
            ):
                continue
            new_id = "evo_append"
            if any(node.node_id == new_id for node in parent.nodes):
                continue
            add(
                (*parent.nodes, SkillNode(new_id, binding.binding_id)),
                (*parent.edges, SkillEdge(parent.output_node, new_id)),
                new_id,
                f"append_{binding.binding_id.replace('.', '_')}",
            )
            if len(variants) >= limit:
                break
        return variants
