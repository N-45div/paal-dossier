// Latest read wins: a read applies only if no later-issued read has already applied.
export function createLatestReads() {
  let issued = 0;
  let applied = 0;
  return {
    start() {
      issued += 1;
      return issued;
    },
    // True when this read may update the screen; marks it applied.
    accept(seq) {
      if (seq < applied) return false;
      applied = seq;
      return true;
    },
  };
}
