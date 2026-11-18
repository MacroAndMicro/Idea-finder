package com.idea_finder.repo.domain;

/** IF-45: aggregate pipeline funnel counts (projection of {@link RawSignalRepository#pipelineCounts()}). */
public interface PipelineCounts {

	long getEmbeddedSignals();

	long getExtractedSignals();

	long getPainPoints();

	long getB2bPainPoints();

	long getFailedExtractions();
}
