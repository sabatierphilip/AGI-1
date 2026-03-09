; ARACHNE Persistent Rule Base
; Includes pre-seeded ontological, causal, temporal, epistemic, conversational, meta, and self-referential rules.

(deftemplate nars-score
  (slot key)
  (slot frequency (default 0.5))
  (slot confidence (default 0.5))
  (slot source (default "internal")))

(deftemplate entity (slot name) (slot kind))
(deftemplate relation (slot subject) (slot predicate) (slot object) (slot confidence))
(deftemplate intent (slot type) (slot text))
(deftemplate conversation-topic (slot topic))
(deftemplate contradiction (slot lhs) (slot rhs))
(deftemplate clarification-needed (slot reason))
(deftemplate rule-health (slot rule-name) (slot confidence) (slot support) (slot contradict))
(deftemplate induced-candidate (slot signature) (slot support) (slot confidence))
(deftemplate self-state (slot key) (slot value))
(deftemplate conclusion (slot text) (slot trace-id))
(deftemplate verbalization-template (slot pattern) (slot template))

; ---------------- Ontological rules (8) ----------------
(defrule ontological-is-a
  (declare (salience 100))
  (relation (subject ?x) (predicate "is-a") (object ?y))
  =>
  (assert (entity (name ?x) (kind ?y))))

(defrule ontological-instance-of
  (declare (salience 95))
  (relation (subject ?x) (predicate "instance-of") (object ?y))
  =>
  (assert (entity (name ?x) (kind ?y))))

(defrule ontological-has-a
  (relation (subject ?x) (predicate "has-a") (object ?y))
  =>
  (assert (relation (subject ?y) (predicate "part-of") (object ?x) (confidence 0.7))))

(defrule ontological-part-of-transitive
  (relation (subject ?a) (predicate "part-of") (object ?b))
  (relation (subject ?b) (predicate "part-of") (object ?c))
  =>
  (assert (relation (subject ?a) (predicate "part-of") (object ?c) (confidence 0.65))))

(defrule ontological-kind-propagation
  (entity (name ?x) (kind ?y))
  (relation (subject ?y) (predicate "is-a") (object ?z))
  =>
  (assert (entity (name ?x) (kind ?z))))

(defrule ontological-unknown-entity
  (declare (salience 90))
  (intent (type "ASSERT") (text ?txt))
  (not (entity (name ?txt) (kind ?)))
  =>
  (assert (self-state (key "unknown_entity") (value ?txt))))

(defrule ontological-instance-kind-link
  (relation (subject ?x) (predicate "instance-of") (object ?y))
  =>
  (assert (relation (subject ?x) (predicate "is-a") (object ?y) (confidence 0.85))))

(defrule ontological-taxonomy-observe
  (entity (name ?x) (kind ?k))
  =>
  (assert (self-state (key "taxonomy_seen") (value ?k))))

; ---------------- Causal rules (7) ----------------
(defrule causal-causes-implies-before
  (relation (subject ?a) (predicate "causes") (object ?b))
  =>
  (assert (relation (subject ?a) (predicate "before") (object ?b) (confidence 0.7))))

(defrule causal-prevents-contradiction
  (relation (subject ?a) (predicate "prevents") (object ?b))
  (relation (subject ?a) (predicate "causes") (object ?b))
  =>
  (assert (contradiction (lhs ?a) (rhs ?b))))

(defrule causal-requires-link
  (relation (subject ?a) (predicate "requires") (object ?b))
  =>
  (assert (relation (subject ?b) (predicate "enables") (object ?a) (confidence 0.7))))

(defrule causal-chain
  (relation (subject ?a) (predicate "causes") (object ?b))
  (relation (subject ?b) (predicate "causes") (object ?c))
  =>
  (assert (relation (subject ?a) (predicate "causes") (object ?c) (confidence 0.6))))

(defrule causal-enables-soft-cause
  (relation (subject ?a) (predicate "enables") (object ?b))
  =>
  (assert (relation (subject ?a) (predicate "supports") (object ?b) (confidence 0.55))))

(defrule causal-requirement-gap
  (relation (subject ?a) (predicate "requires") (object ?b))
  (not (relation (subject ?b) (predicate "available") (object ?a)))
  =>
  (assert (clarification-needed (reason "required_precondition_missing"))))

(defrule causal-precondition-satisfied
  (relation (subject ?a) (predicate "requires") (object ?b))
  (relation (subject ?b) (predicate "available") (object ?a))
  =>
  (assert (conclusion (text "precondition-satisfied") (trace-id "causal-precondition-satisfied"))))

; ---------------- Temporal rules (5) ----------------
(defrule temporal-before-after
  (relation (subject ?x) (predicate "before") (object ?y))
  =>
  (assert (relation (subject ?y) (predicate "after") (object ?x) (confidence 0.75))))

(defrule temporal-sequence-transitive
  (relation (subject ?x) (predicate "before") (object ?y))
  (relation (subject ?y) (predicate "before") (object ?z))
  =>
  (assert (relation (subject ?x) (predicate "before") (object ?z) (confidence 0.65))))

(defrule temporal-during-inclusion
  (relation (subject ?x) (predicate "during") (object ?y))
  =>
  (assert (relation (subject ?x) (predicate "part-of") (object ?y) (confidence 0.6))))

(defrule temporal-sequence-detected
  (relation (subject ?a) (predicate "sequence") (object ?b))
  =>
  (assert (relation (subject ?a) (predicate "before") (object ?b) (confidence 0.6))))

(defrule temporal-epistemic-staleness
  (relation (subject ?claim) (predicate "before") (object "now"))
  =>
  (assert (self-state (key "possibly_stale") (value ?claim))))

; ---------------- Epistemic rules (6) ----------------
(defrule epistemic-belief-register
  (relation (subject ?agent) (predicate "believes") (object ?claim))
  =>
  (assert (rule-health (rule-name ?claim) (confidence 0.6) (support 1) (contradict 0))))

(defrule epistemic-doubt-lowers-confidence
  ?rh <- (rule-health (rule-name ?r) (confidence ?c) (support ?s) (contradict ?k))
  (relation (subject ?agent) (predicate "doubts") (object ?r))
  =>
  (modify ?rh (confidence (- ?c 0.1)) (contradict (+ ?k 1))))

(defrule epistemic-confirm-raises-confidence
  ?rh <- (rule-health (rule-name ?r) (confidence ?c) (support ?s) (contradict ?k))
  (relation (subject ?agent) (predicate "confirms") (object ?r))
  =>
  (modify ?rh (confidence (+ ?c 0.05)) (support (+ ?s 1))))

(defrule epistemic-source-attribution
  (relation (subject ?claim) (predicate "source-attribution") (object ?src))
  =>
  (assert (self-state (key "source") (value ?src))))

(defrule epistemic-contradiction-detected
  (relation (subject ?x) (predicate ?p) (object ?y))
  (relation (subject ?x) (predicate (neq ?p ?q)) (object ?y))
  =>
  (assert (contradiction (lhs ?p) (rhs ?q))))

(defrule epistemic-high-confidence-conclusion
  (rule-health (rule-name ?r) (confidence ?c&:(> ?c 0.8)))
  =>
  (assert (conclusion (text ?r) (trace-id "epistemic-high-confidence"))))

; ---------------- Conversational rules (6) ----------------
(defrule conversational-track-topic
  (intent (type "QUERY") (text ?txt))
  =>
  (assert (conversation-topic (topic ?txt))))

(defrule conversational-intent-resolution
  (intent (type "CLARIFY") (text ?t))
  =>
  (assert (clarification-needed (reason ?t))))

(defrule conversational-contradiction-alert
  (intent (type "CONTRADICT") (text ?t))
  =>
  (assert (contradiction (lhs ?t) (rhs "conversation"))))

(defrule conversational-clarification-request
  (contradiction (lhs ?x) (rhs ?y))
  =>
  (assert (conclusion (text "Please clarify contradiction") (trace-id "conversation-clarify"))))

(defrule conversational-topic-followup
  (conversation-topic (topic ?t))
  (intent (type "QUERY") (text ?q))
  =>
  (assert (relation (subject ?q) (predicate "about") (object ?t) (confidence 0.65))))

(defrule conversational-unknown-intent
  (intent (type "UNKNOWN") (text ?t))
  =>
  (assert (clarification-needed (reason "unknown_intent"))))

; ---------------- Meta-rules (5) ----------------
(defrule meta-rule-confidence-drop-retract
  ?rh <- (rule-health (rule-name ?r) (confidence ?c&:(< ?c 0.3)))
  =>
  (retract ?rh)
  (assert (self-state (key "rule_retracted") (value ?r))))

(defrule meta-rule-induce-when-supported
  (induced-candidate (signature ?sig) (support ?s&:(>= ?s 3)) (confidence ?c&:(>= ?c 0.6)))
  =>
  (assert (conclusion (text ?sig) (trace-id "meta-induce"))))

(defrule meta-rule-quarantine-low-confidence
  (induced-candidate (signature ?sig) (confidence ?c&:(< ?c 0.6)))
  =>
  (assert (self-state (key "quarantined_rule") (value ?sig))))

(defrule meta-rule-track-health
  (rule-health (rule-name ?r) (confidence ?c))
  =>
  (assert (self-state (key "rule-health") (value ?r))))

(defrule meta-rule-overfit-guard
  (rule-health (rule-name ?r) (support ?s&:(> ?s 20)) (contradict ?k&:(> ?k 5)))
  =>
  (assert (self-state (key "overfit-warning") (value ?r))))

; ---------------- Self-referential rules (5) ----------------
(defrule self-knowledge-gap
  (clarification-needed (reason ?r))
  =>
  (assert (self-state (key "knowledge_gap") (value ?r))))

(defrule self-observe-rulebase
  (self-state (key "rule-health") (value ?r))
  =>
  (assert (relation (subject "arachne") (predicate "believes") (object ?r) (confidence 0.7))))

(defrule self-audit-quarantine
  (self-state (key "quarantined_rule") (value ?r))
  =>
  (assert (relation (subject "arachne") (predicate "doubts") (object ?r) (confidence 0.65))))

(defrule self-gap-report
  (self-state (key "knowledge_gap") (value ?g))
  =>
  (assert (conclusion (text "I have a conclusion but no verbalization rule for it yet") (trace-id "self-gap-report"))))

(defrule self-rule-count
  (declare (salience -10))
  (self-state (key "startup") (value "ready"))
  =>
  (assert (conclusion (text "rulebase-active") (trace-id "self-rule-count"))))

; ---------------- Verbalization templates (default seed) ----------------
(deffacts templates
  (verbalization-template (pattern "precondition-satisfied") (template "The required precondition appears to be satisfied."))
  (verbalization-template (pattern "Please clarify contradiction") (template "I found conflicting statements. Can you clarify?"))
  (verbalization-template (pattern "rulebase-active") (template "My rulebase is active and monitoring this conversation.")))
