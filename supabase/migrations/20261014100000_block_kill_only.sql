-- Fantasy: a block scores only when it wins the point (owner, 2026-10-14).
--
-- G1 as ratified (2026-09-27) reads "Block +1 (kill block +1 / soft block 0)",
-- but the seeded rule gave +1 to ANY block. No block was ever published -- the
-- post-run layer has no block label -- so no score moves today. Blocks now
-- arrive through the owner's review of a match (`make review`,
-- src/publish/reviewed.py): a block that ends the point for the blocker's
-- team is published with outcome `kill`, any other block with none.
--
-- Only a rule still as seeded is changed: a rule set an admin edited keeps
-- what the admin chose. `src/publish/fantasy.py` (G1_RULES) and the demo mode
-- (`webapp/src/lib/demo.ts`) mirror the rule; `tests/test_publish.py` and
-- `supabase/checks/rls_smoke.sql` pin it.

update public.fantasy_rules
set outcome = 'kill', label = 'Kill block'
where rule_key = 'block' and outcome is null and actions = array['block'];
