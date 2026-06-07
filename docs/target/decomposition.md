# Evaluation Decomposition

If full-puzzle performance falls below a useful threshold, the target benchmark can be decomposed into narrower tasks.

## Components

1. **Membership**

   Decide whether a sequence belongs to the formal language.

2. **Generation**

   Produce a sequence that belongs to the formal language.

3. **Tile Constraint**

   Determine whether a candidate can be formed from the available rack symbols and board overlap.

4. **Placement**

   Place a supplied valid sequence on the board according to geometric rules.

5. **Cross-Words**

   Verify that all perpendicular sequences created by a placement are valid.

6. **Output Schema**

   Encode an otherwise known-valid move in the required structured format.

This decomposition helps distinguish failures of language induction, search, spatial reasoning, constraint satisfaction, and serialization.

It is not part of V1. V1 evaluates only the complete move-generation task.
