# Parser Bugs Discovered During Test Suite Improvement

This document tracks parser issues discovered while adding edge case tests.
These bugs should be addressed separately from the test suite improvement work.

## Episode Extraction Bugs

### BUG-EP-001: OVA episodes without dash separator not extracted

**Test Case Input**: `[Group] Title OVA 01 [1080p]`
**Expected Behavior**: Episode should be extracted as `1.0`
**Actual Behavior**: Returns `(None, None)` - no episode found

**Related Test Methods**:
- `TestEpisodeEdgeCases.test_ova_with_episode[ova_with_episode_01]`
- `TestEpisodeEdgeCases.test_ova_with_episode[ova_with_episode_02]`

**Analysis**: The parser only extracts episodes when there's a dash separator before the number (e.g., `OVA - 01`). Without the dash, the `OVA 01` pattern is not recognized.

**Workaround**: Use format `[Group] Title OVA - 01 [1080p]` which works correctly.

---

### BUG-EP-002: OAD format not supported

**Test Case Input**: `[Group] Title OAD 01 [1080p]`
**Expected Behavior**: Episode should be extracted as `1.0`
**Actual Behavior**: Returns `(None, None)` - no episode found

**Related Test Methods**:
- `TestEpisodeEdgeCases.test_ova_with_episode[oad_with_episode_01]`

**Analysis**: OAD (Original Animation DVD) is a common release format similar to OVA, but the parser does not recognize the `OAD` keyword followed by an episode number.

---

### BUG-EP-003: SP (Special) prefix episodes not extracted

**Test Case Inputs**:
- `[Group] Title - SP01 [1080p]`
- `[Group] Title SP02 [1080p]`
- `[Group] Title [SP01] [1080p]`

**Expected Behavior**: Episode should be extracted as the number following `SP`
**Actual Behavior**: Returns `(None, None)` - no episode found

**Related Test Methods**:
- `TestEpisodeEdgeCases.test_sp_prefix_episodes[sp_prefix_01]`
- `TestEpisodeEdgeCases.test_sp_prefix_episodes[sp_prefix_02_no_dash]`
- `TestEpisodeEdgeCases.test_sp_prefix_episodes[sp_prefix_bracketed]`

**Analysis**: The `SP` (Special) prefix is commonly used for special episodes, side stories, and bonus content. The parser does not recognize `SP` followed by a number as a valid episode pattern.

**Priority**: Medium - SP episodes are common in anime releases, especially for seasonal bonus content.

---

## Season Extraction Bugs

### BUG-SE-001: S00E01 format not supported (Season 0)

**Test Case Input**: `[Group] Title S00E01 [1080p]`
**Expected Behavior**: Season should be extracted as `0`
**Actual Behavior**: Returns `1` - default value instead of actual season 0

**Related Test Methods**:
- `TestSeasonBracketEdgeCases.test_season_zero[season_zero_s00e01]`

**Analysis**: The `S00E01` pattern (where season and episode are combined without spaces) does not correctly extract season 0. However, `S00 - 01` (with dash separator) and `Season 0 - 01` both work correctly.

**Note**: Season 0 is commonly used for specials, extras, and behind-the-scenes content in many media databases (e.g., TVDB, TMDB).

**Priority**: Low - Workaround exists using dash separator format.

---

## Bracket Handling Bugs

### BUG-BR-001: Deeply nested brackets not handled correctly

**Test Case Input**: `[Group [[Nested]]] Title - 01 [1080p]`
**Expected Behavior**: Group should be extracted as `Group [[Nested]]`
**Actual Behavior**: Extraction fails or returns incorrect group name

**Related Test Methods**:
- `TestSeasonBracketEdgeCases.test_deeply_nested_brackets[nested_brackets_in_group]`

**Analysis**: When brackets are nested within the group name bracket (e.g., sub-groups or collaboration indicators), the parser may not correctly identify the group boundary.

**Priority**: Low - Uncommon edge case.

---

### BUG-BR-002: Double bracket start not handled

**Test Case Input**: `[[Double]] Title - 01 [1080p]`
**Expected Behavior**: Group should be extracted as `[Double]`
**Actual Behavior**: Extraction fails or returns incorrect group name

**Related Test Methods**:
- `TestSeasonBracketEdgeCases.test_deeply_nested_brackets[double_bracket_start]`

**Analysis**: When a torrent name starts with double brackets `[[`, the parser does not correctly handle the inner bracket as part of the group name.

**Priority**: Low - Very uncommon edge case.

---

## Raw Parser Title Bugs

### BUG-RP-001: NieR:Automata colon in title not parsed correctly

**Test Case Input**: `[织梦字幕组][尼尔：机械纪元 NieR Automata Ver1.1a][02集][1080P][AVC][简日双语]`
**Expected Behavior**: 
- `title_zh` = `尼尔：机械纪元`
- `title_en` = `NieR Automata Ver1.1a`
**Actual Behavior**: 
- `title_zh` = `[尼尔：机械纪元Ver1.1a][02集]`
- `title_en` = `NieR Automata`

**Related Test Methods**:
- `TestRawParserKnownIssues.test_nier_automata_colon_in_title`

**Analysis**: When the Chinese title contains a colon (：) and is followed by English title with version info, the parser incorrectly groups additional brackets into the Chinese title.

**Priority**: Medium - Affects real-world RSS feeds from popular fansub groups.

---

### BUG-RP-002: Tilde-decorated English titles stripped

**Test Case Input**: `【喵萌奶茶屋】★07月新番★[银砂糖师与黑妖精 ~ Sugar Apple Fairy Tale ~][13][1080p][简日双语][招募翻译]`
**Expected Behavior**: `title_en` = `~ Sugar Apple Fairy Tale ~`
**Actual Behavior**: `title_en` = `Sugar Apple Fairy Tale`

**Related Test Methods**:
- `TestRawParserKnownIssues.test_sugar_apple_tilde_title`

**Analysis**: Leading and trailing tilde decorations are stripped from the English title, losing the stylized formatting used by the official release.

**Priority**: Low - Cosmetic issue, title content is preserved.

---

### BUG-RP-003: Titles starting with numbers not parsed correctly

**Test Case Input**: `[ANi]  16bit 的感动 ANOTHER LAYER - 01 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]`
**Expected Behavior**: `title_zh` = `16bit 的感动 ANOTHER LAYER`
**Actual Behavior**: `title_zh` = `的感动`

**Related Test Methods**:
- `TestRawParserKnownIssues.test_16bit_number_at_start`

**Analysis**: When the title starts with a number (e.g., "16bit"), the parser incorrectly splits the title, treating the number as something else and leaving only partial Chinese text.

**Priority**: Medium - Affects anime titles that start with numbers (e.g., "86", "07-Ghost", "009 Re:Cyborg").

---

## Summary

| Bug ID | Description | Severity | Status |
|--------|-------------|----------|--------|
| BUG-EP-001 | OVA without dash not supported | Low | **Fixed** |
| BUG-EP-002 | OAD format not supported | Low | **Fixed** |
| BUG-EP-003 | SP prefix not supported | Medium | **Fixed** |
| BUG-SE-001 | S00E01 format not supported | Low | **Fixed** |
| BUG-BR-001 | Nested brackets not handled | Low | Open |
| BUG-BR-002 | Double bracket start not handled | Low | Open |
| BUG-RP-001 | NieR:Automata colon parsing | Medium | **Fixed** |
| BUG-RP-002 | Tilde-decorated titles stripped | Low | **Fixed** |
| BUG-RP-003 | Titles starting with numbers | Medium | **Fixed** |

**7 of 9 bugs have been fixed.** The remaining 2 bugs (BUG-BR-001, BUG-BR-002) are low-priority bracket handling edge cases that are still marked with `pytest.mark.xfail` in the test suite.
