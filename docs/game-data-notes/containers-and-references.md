# Containers, identity, and references

This page describes the serialized conventions observed in the private `Resistsave00070_2041-5-1.json` sample on 2026-09-08. It is the decoding guide for the `terra_invicta_json_v1` envelope documented in [the format note](terra_invicta_json_v1.md).

## Observed facts

### Typed-state map encoding

`gamestates` maps a serialized state-type name to a container. A populated container is an array of pairs in this shape:

```json
[
  {
    "Key": { "value": 123 },
    "Value": {
      "ID": { "value": 123 },
      "...": "state-specific fields"
    }
  }
]
```

The actual numeric IDs and data are omitted above. In the inspected sample:

- 67 populated state-type containers used this pair-array form.
- All 15,525 inspected pairs had `Key.value` and `Value.ID.value` as integer values, and those values were equal.
- Nine empty state-type containers were serialized as an empty object (`{}`), not an empty array. They were `TIWarState`, `TIMegafaunaArmyState`, `TISpaceCombatState`, `TISpaceCombatProjectileState`, and the empty `FactionGoal_*` containers `BuildMiningBase`, `BuildRefuellingStation`, `RefitFleet`, `ResupplyFleet`, and `TruceWithFaction`.

This is not ordinary JSON object-map syntax. A generic parser must normalize both encodings before a domain parser sees a state collection:

```text
{}                         -> empty mapping
[{Key: {value: id},
  Value: {ID: {value: id}}] -> mapping[int id, object value]
```

Reject a non-empty container whose entries do not have this shape, or whose two IDs disagree, as an unsupported serialized representation. Do not infer an identity from display text when the key/ID invariant is available.

### References and nullable relationships

Many relationships use an object with a `value` member whose value is an integer ID. This was directly observed for faction, nation, region, fleet, hab, orbit, ship, and control-point references. Relationship fields can also be `null`; for example, the sampled first control point had no `faction` and the sampled first councilor had no `faction`.

Arrays occur for both relationship collections and scalar collections. For example, faction `councilors` and `controlPoints`, fleet `ships`, and hab `sectors` had first elements shaped as `{ "value": ... }`; global research `finishedTechsNames` had string elements. An array must therefore be decoded from its owning field's documented meaning, not merely from its JSON type.

Some reference-shaped objects also had a `$type` member (observed in `TICouncilorState.location` and `TISpaceFleetState.barycenter`). Preserve that discriminator until the relevant domain parser has a documented use for it.

### Field-level dictionaries

Observed on 2026-10-13 in five private complete saves (structure only): a dictionary-valued *field* on a state object follows the same convention as the state-type containers. A non-empty dictionary is an array of `{ "Key": ..., "Value": ... }` pairs whose `Key` is a reference object (`{ "value": id }`, sometimes with `$type`), and an empty dictionary is `{}`. The same field is therefore seen as an array on some entities and as an object on others: `TIFactionState.Kills`, `factionAssassinations`, `internalCouncilorSuspicion`, `nShipyardQueues`, `TICouncilorState.assassinations`, `TINationState.adjacentNations`, `rivalryCooldowns`, `improveRelationsCooldowns`, `factionUnrestAttempts`. Dictionaries that were never empty in the sample (`TIFactionState.lostControlPoints`, `knownAlienSites`, `factionHate`) appeared only in the array form. A field-level decoder must accept both forms; the normalizer does not decode these fields yet.

### Common entity metadata

The inspected entity values included `ID`, `archived`, `exists`, `finderSortOverride`, `templateName`, `displayName`, and `$type` alongside domain-specific fields. These fields are serialized data, not a promise that every future state type will have exactly this set.

## Recommended normalization contract

The following is a project contract derived from the observations, rather than a claim about the game implementation:

1. Parse JSON without transforming values.
2. Select a `gamestates` state type by its exact string key.
3. Convert its `{}` or pair-array container to an ID-keyed mapping.
4. Verify pair key equals `Value.ID` when an entry is present.
5. Keep IDs as integers internally; stringify only at a public event or rendering boundary when needed.
6. Retain nullable references as `None` and unresolved IDs as references; never replace them with invented entities.
7. Preserve unknown state-type containers as raw data so a new game version cannot silently lose information.

## Hypotheses and limits

- The `{}`-for-empty convention appears to be a serializer behavior. It has since been observed in six complete saves, at the container level and at the field level, but a future format may still emit `[]`.
- Equality of map key and `Value.ID` is a strong observed invariant, not proof that every possible game object or future build uses it.
- `$type` may distinguish polymorphic reference targets. Its semantics are not yet mapped.
