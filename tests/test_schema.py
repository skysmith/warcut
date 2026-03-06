from scw_builder.episode_schema import load_episode


def test_load_episode():
    episode = load_episode("episodes/ep01.yaml")
    assert episode.id == "ep01"
    assert len(episode.beats) == 3
