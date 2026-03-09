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
  (relation (subject ?x) (predicate ?q&:(neq ?p ?q)) (object ?y))
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

; ---------------- Expanded Ontological rules (15) ----------------
(defrule ontological-sibling-type
  (entity (name ?a) (kind ?k))
  (entity (name ?b&:(neq ?a ?b)) (kind ?k))
  =>
  (assert (relation (subject ?a) (predicate "sibling-type") (object ?b) (confidence 0.6))))

(defrule ontological-abstract-classification
  (entity (name ?x) (kind ?k&:(or (eq ?k "concept") (eq ?k "idea") (eq ?k "theory"))))
  =>
  (assert (relation (subject ?x) (predicate "classification") (object "abstract") (confidence 0.7))))

(defrule ontological-concrete-classification
  (entity (name ?x) (kind ?k&:(or (eq ?k "object") (eq ?k "tool") (eq ?k "organism"))))
  =>
  (assert (relation (subject ?x) (predicate "classification") (object "concrete") (confidence 0.7))))

(defrule ontological-multiple-inheritance-flatten-1
  (entity (name ?x) (kind ?k1))
  (relation (subject ?k1) (predicate "is-a") (object ?k2))
  =>
  (assert (entity (name ?x) (kind ?k2))))

(defrule ontological-multiple-inheritance-flatten-2
  (entity (name ?x) (kind ?k1))
  (relation (subject ?k1) (predicate "instance-of") (object ?k2))
  =>
  (assert (entity (name ?x) (kind ?k2))))

(defrule ontological-kind-chain-conclusion
  (entity (name ?x) (kind ?k1))
  (relation (subject ?k1) (predicate "is-a") (object ?k2))
  =>
  (assert (conclusion (text "kind-chain") (trace-id "ontological-kind-chain-conclusion"))))

(defrule ontological-disambiguate-shared-kind
  (entity (name ?a) (kind ?k))
  (entity (name ?b&:(neq ?a ?b)) (kind ?k))
  =>
  (assert (self-state (key "disambiguation-needed") (value ?k))))

(defrule ontological-taxonomy-depth-1
  (entity (name ?x) (kind ?k1))
  (relation (subject ?k1) (predicate "is-a") (object ?k2))
  =>
  (assert (self-state (key "taxonomy-depth") (value "1"))))

(defrule ontological-taxonomy-depth-2
  (entity (name ?x) (kind ?k1))
  (relation (subject ?k1) (predicate "is-a") (object ?k2))
  (relation (subject ?k2) (predicate "is-a") (object ?k3))
  =>
  (assert (self-state (key "taxonomy-depth") (value "2"))))

(defrule ontological-unknown-kind-escalation
  (entity (name ?x) (kind "unknown"))
  =>
  (assert (clarification-needed (reason "unknown-kind"))))

(defrule ontological-cross-source-reconcile
  (relation (subject ?x) (predicate "wikidata-match") (object ?y))
  (relation (subject ?x) (predicate "is-a") (object ?k))
  (relation (subject ?y) (predicate "is-a") (object ?k))
  =>
  (assert (relation (subject ?x) (predicate "same-kind-as") (object ?y) (confidence 0.78))))

(defrule ontological-instance-conclusion
  (relation (subject ?x) (predicate "instance-of") (object ?k))
  =>
  (assert (conclusion (text "instance-recognized") (trace-id "ontological-instance-conclusion"))))

(defrule ontological-kind-membership-conclusion
  (entity (name ?x) (kind ?k))
  =>
  (assert (conclusion (text "kind-membership") (trace-id "ontological-kind-membership-conclusion"))))

(defrule ontological-kind-proxy-contains
  (entity (name ?x) (kind ?k))
  =>
  (assert (relation (subject ?k) (predicate "contains-entity") (object ?x) (confidence 0.58))))

(defrule ontological-taxonomy-monitor
  (entity (name ?x) (kind ?k))
  =>
  (assert (self-state (key "taxonomy-monitor") (value ?k))))

; ---------------- Expanded Causal rules (12) ----------------
(defrule causal-indirect-causation
  (relation (subject ?a) (predicate "enables") (object ?b))
  (relation (subject ?b) (predicate "causes") (object ?c))
  =>
  (assert (relation (subject ?a) (predicate "indirectly-causes") (object ?c) (confidence 0.62))))

(defrule causal-mutual-detection
  (relation (subject ?a) (predicate "causes") (object ?b))
  (relation (subject ?b) (predicate "causes") (object ?a))
  =>
  (assert (self-state (key "mutual-causation") (value ?a))))

(defrule causal-loop-contradiction
  (relation (subject ?a) (predicate "causes") (object ?b))
  (relation (subject ?b) (predicate "causes") (object ?a))
  =>
  (assert (contradiction (lhs ?a) (rhs ?b))))

(defrule causal-negative-causation
  (relation (subject ?a) (predicate "prevents") (object ?b))
  (relation (subject ?c) (predicate "requires") (object ?b))
  =>
  (assert (relation (subject ?a) (predicate "blocks") (object ?c) (confidence 0.62))))

(defrule causal-chain-length-2
  (relation (subject ?a) (predicate "causes") (object ?b))
  (relation (subject ?b) (predicate "causes") (object ?c))
  =>
  (assert (self-state (key "causal-chain-length") (value "2"))))

(defrule causal-chain-length-3
  (relation (subject ?a) (predicate "causes") (object ?b))
  (relation (subject ?b) (predicate "causes") (object ?c))
  (relation (subject ?c) (predicate "causes") (object ?d))
  =>
  (assert (self-state (key "causal-chain-length") (value "3"))))

(defrule causal-weakening-hop-1
  (relation (subject ?a) (predicate "causes") (object ?b) (confidence ?c))
  =>
  (assert (relation (subject ?a) (predicate "cause-strength") (object ?b) (confidence (- ?c 0.08)))))

(defrule causal-root-cause
  (relation (subject ?a) (predicate "causes") (object ?b))
  (not (relation (subject ?x) (predicate "causes") (object ?a)))
  =>
  (assert (conclusion (text "root-cause-identified") (trace-id "causal-root-cause"))))

(defrule causal-leaf-effect
  (relation (subject ?a) (predicate "causes") (object ?b))
  (not (relation (subject ?b) (predicate "causes") (object ?c)))
  =>
  (assert (conclusion (text "leaf-effect-identified") (trace-id "causal-leaf-effect"))))

(defrule causal-enable-before
  (relation (subject ?a) (predicate "enables") (object ?b))
  =>
  (assert (relation (subject ?a) (predicate "before") (object ?b) (confidence 0.59))))

(defrule causal-cause-transitive-observed
  (relation (subject ?a) (predicate "causes") (object ?b))
  (relation (subject ?b) (predicate "causes") (object ?c))
  =>
  (assert (conclusion (text "causes-transitive-observed") (trace-id "causal-cause-transitive-observed"))))

(defrule causal-support-branch
  (relation (subject ?a) (predicate "supports") (object ?b))
  =>
  (assert (self-state (key "causal-support") (value ?b))))

; ---------------- Expanded Temporal rules (10) ----------------
(defrule temporal-overlap-cooccur
  (relation (subject ?a) (predicate "during") (object ?b))
  (relation (subject ?c&:(neq ?a ?c)) (predicate "during") (object ?b))
  =>
  (assert (relation (subject ?a) (predicate "co-occur") (object ?c) (confidence 0.67))))

(defrule temporal-contradiction-before
  (relation (subject ?a) (predicate "before") (object ?b))
  (relation (subject ?b) (predicate "before") (object ?a))
  =>
  (assert (contradiction (lhs ?a) (rhs ?b))))

(defrule temporal-cluster-1
  (relation (subject ?a) (predicate "before") (object ?t))
  (relation (subject ?b&:(neq ?a ?b)) (predicate "before") (object ?t))
  (relation (subject ?c&:(and (neq ?a ?c) (neq ?b ?c))) (predicate "before") (object ?t))
  =>
  (assert (conclusion (text "group-precedes-target") (trace-id "temporal-cluster-1"))))

(defrule temporal-deadline-inference
  (relation (subject ?a) (predicate "requires") (object ?b))
  (relation (subject ?b) (predicate "before") (object ?a))
  =>
  (assert (relation (subject ?b) (predicate "is-prerequisite-for") (object ?a) (confidence 0.74))))

(defrule temporal-gap-detection
  (relation (subject ?a) (predicate "before") (object ?c))
  (not (relation (subject ?a) (predicate "before") (object ?b)))
  =>
  (assert (conclusion (text "direct-sequence") (trace-id "temporal-gap-detection"))))

(defrule temporal-after-before
  (relation (subject ?a) (predicate "after") (object ?b))
  =>
  (assert (relation (subject ?b) (predicate "before") (object ?a) (confidence 0.73))))

(defrule temporal-sync-window
  (relation (subject ?a) (predicate "co-occur") (object ?b))
  =>
  (assert (self-state (key "temporal-window") (value "co-occur"))))

(defrule temporal-sequence-summary
  (relation (subject ?a) (predicate "before") (object ?b))
  =>
  (assert (conclusion (text "sequence-known") (trace-id "temporal-sequence-summary"))))

(defrule temporal-priority-mark
  (relation (subject ?a) (predicate "is-prerequisite-for") (object ?b))
  =>
  (assert (self-state (key "priority-item") (value ?a))))

(defrule temporal-now-grounding
  (relation (subject ?x) (predicate "before") (object "now"))
  =>
  (assert (self-state (key "timeline-grounded") (value ?x))))

; ---------------- Expanded Epistemic rules (12) ----------------
(defrule epistemic-second-order-belief
  (relation (subject ?a) (predicate "believes") (object ?b))
  (relation (subject ?b) (predicate "believes") (object ?c))
  =>
  (assert (relation (subject ?a) (predicate "indirectly-believes") (object ?c) (confidence 0.56))))

(defrule epistemic-belief-decay
  (relation (subject ?a) (predicate "indirectly-believes") (object ?c) (confidence ?conf))
  =>
  (assert (relation (subject ?a) (predicate "believes") (object ?c) (confidence (- ?conf 0.07)))))

(defrule epistemic-source-triangulation
  (relation (subject ?s1) (predicate "confirms") (object ?claim))
  (relation (subject ?s2&:(neq ?s1 ?s2)) (predicate "confirms") (object ?claim))
  (relation (subject ?s3&:(and (neq ?s1 ?s3) (neq ?s2 ?s3))) (predicate "confirms") (object ?claim))
  =>
  (assert (conclusion (text "high-confidence-claim") (trace-id "epistemic-source-triangulation"))))

(defrule epistemic-conflicting-sources
  (relation (subject ?a) (predicate ?p1) (object ?o))
  (relation (subject ?a) (predicate ?p2&:(neq ?p1 ?p2)) (object ?o))
  =>
  (assert (self-state (key "source-conflict") (value ?a))))

(defrule epistemic-doubt-cascade
  (relation (subject ?agent) (predicate "doubts") (object ?claim))
  (relation (subject ?claim) (predicate "enables") (object ?other))
  =>
  (assert (relation (subject ?agent) (predicate "doubts") (object ?other) (confidence 0.52))))

(defrule epistemic-over-confirmation
  (relation (subject ?agent) (predicate "confirms") (object ?c))
  (relation (subject ?agent) (predicate "confirms") (object ?c))
  (relation (subject ?agent) (predicate "confirms") (object ?c))
  (relation (subject ?agent) (predicate "confirms") (object ?c))
  (relation (subject ?agent) (predicate "confirms") (object ?c))
  =>
  (assert (self-state (key "over-confirmation") (value ?agent))))

(defrule epistemic-closure-detection
  (relation (subject ?agent) (predicate "believes") (object ?c1))
  (relation (subject ?agent) (predicate "believes") (object ?c2))
  =>
  (assert (self-state (key "epistemic-closure") (value ?agent))))

(defrule epistemic-claim-recorded
  (relation (subject ?agent) (predicate "believes") (object ?claim))
  =>
  (assert (conclusion (text "belief-recorded") (trace-id "epistemic-claim-recorded"))))

(defrule epistemic-confidence-up
  ?rh <- (rule-health (rule-name ?r) (confidence ?c) (support ?s) (contradict ?k))
  (relation (subject ?a) (predicate "confirms") (object ?r))
  =>
  (modify ?rh (confidence (+ ?c 0.03)) (support (+ ?s 1))))

(defrule epistemic-confidence-down
  ?rh <- (rule-health (rule-name ?r) (confidence ?c) (support ?s) (contradict ?k))
  (relation (subject ?a) (predicate "doubts") (object ?r))
  =>
  (modify ?rh (confidence (- ?c 0.05)) (contradict (+ ?k 1))))

(defrule epistemic-source-audit
  (self-state (key "source-conflict") (value ?x))
  =>
  (assert (conclusion (text "source-conflict") (trace-id "epistemic-source-audit"))))

(defrule epistemic-overconfirmation-audit
  (self-state (key "over-confirmation") (value ?x))
  =>
  (assert (conclusion (text "over-confirmation") (trace-id "epistemic-overconfirmation-audit"))))

; ---------------- Expanded Conversational rules (15) ----------------
(defrule conversational-topic-continuity
  (conversation-topic (topic ?t))
  (intent (type "QUERY") (text ?t))
  =>
  (assert (self-state (key "continuing-topic") (value ?t))))

(defrule conversational-topic-shift
  (conversation-topic (topic ?old))
  (intent (type "QUERY") (text ?new&:(neq ?old ?new)))
  =>
  (assert (self-state (key "topic-shift") (value ?new))))

(defrule conversational-knowledge-gap
  (intent (type "QUERY") (text ?q))
  (not (conclusion (text ?c) (trace-id ?t)))
  =>
  (assert (self-state (key "knowledge-gap") (value ?q))))

(defrule conversational-repetition-detection
  (intent (type ?it) (text ?tx))
  (intent (type ?it) (text ?tx))
  =>
  (assert (self-state (key "repeated-query") (value ?tx))))

(defrule conversational-user-conflict
  (intent (type "ASSERT") (text ?t))
  (intent (type "CONTRADICT") (text ?t))
  =>
  (assert (self-state (key "user-conflict") (value ?t))))

(defrule conversational-greeting
  (intent (type ?it) (text ?t&:(or (neq (str-index "hello" (lowcase ?t)) FALSE) (neq (str-index "hi" (lowcase ?t)) FALSE) (neq (str-index "greetings" (lowcase ?t)) FALSE))))
  =>
  (assert (conclusion (text "greeting-response") (trace-id "conversational-greeting"))))

(defrule conversational-farewell
  (intent (type ?it) (text ?t&:(or (neq (str-index "bye" (lowcase ?t)) FALSE) (neq (str-index "farewell" (lowcase ?t)) FALSE))))
  =>
  (assert (conclusion (text "farewell-response") (trace-id "conversational-farewell"))))

(defrule conversational-clarification-loop-1
  (clarification-needed (reason ?r1))
  (clarification-needed (reason ?r2))
  (clarification-needed (reason ?r3))
  =>
  (assert (self-state (key "escalate-to-gap") (value ?r3))))

(defrule conversational-new-entity
  (relation (subject ?x) (predicate ?p) (object ?y))
  (not (self-state (key "seen-entity") (value ?x)))
  =>
  (assert (self-state (key "new-entity") (value ?x)))
  (assert (self-state (key "seen-entity") (value ?x))))

(defrule conversational-command-intent-tell
  (intent (type ?it) (text ?t&:(eq (str-index "tell me" (lowcase ?t)) 1)))
  =>
  (assert (self-state (key "explain-intent") (value "tell"))))

(defrule conversational-command-intent-explain
  (intent (type ?it) (text ?t&:(eq (str-index "explain" (lowcase ?t)) 1)))
  =>
  (assert (self-state (key "explain-intent") (value "explain"))))

(defrule conversational-command-intent-describe
  (intent (type ?it) (text ?t&:(eq (str-index "describe" (lowcase ?t)) 1)))
  =>
  (assert (self-state (key "explain-intent") (value "describe"))))

(defrule conversational-command-intent-list
  (intent (type ?it) (text ?t&:(eq (str-index "list" (lowcase ?t)) 1)))
  =>
  (assert (self-state (key "explain-intent") (value "list"))))

(defrule conversational-topic-shift-conclusion
  (self-state (key "topic-shift") (value ?v))
  =>
  (assert (conclusion (text "topic-shift") (trace-id "conversational-topic-shift-conclusion"))))

(defrule conversational-knowledge-gap-conclusion
  (self-state (key "knowledge-gap") (value ?v))
  =>
  (assert (conclusion (text "knowledge-gap") (trace-id "conversational-knowledge-gap-conclusion"))))

; ---------------- Expanded Meta rules (12) ----------------
(defrule meta-rule-usage-frequency
  ?rh <- (rule-health (rule-name ?r) (confidence ?c) (support ?s) (contradict ?k))
  =>
  (modify ?rh (support (+ ?s 1))))

(defrule meta-unused-rule-decay
  ?rh <- (rule-health (rule-name ?r) (confidence ?c) (support 0) (contradict ?k))
  =>
  (modify ?rh (confidence (- ?c 0.04))))

(defrule meta-rule-contradiction-detection
  (relation (subject ?x) (predicate ?p1) (object ?y))
  (relation (subject ?x) (predicate ?p2&:(neq ?p1 ?p2)) (object ?y))
  =>
  (assert (self-state (key "rule-conflict") (value ?x))))

(defrule meta-rule-family-coherence
  (relation (subject ?a) (predicate ?p) (object ?b))
  (relation (subject ?c) (predicate ?p) (object ?d))
  =>
  (assert (self-state (key "family-member") (value ?p))))

(defrule meta-induction-rate-monitor
  (self-state (key "ilp-events") (value ?v&:(> ?v 20)))
  =>
  (assert (self-state (key "high-induction-rate") (value ?v))))

(defrule meta-milestone-50
  (self-state (key "rule-count") (value ?v&:(>= ?v 50)))
  =>
  (assert (conclusion (text "milestone-reached") (trace-id "meta-milestone-50"))))

(defrule meta-milestone-100
  (self-state (key "rule-count") (value ?v&:(>= ?v 100)))
  =>
  (assert (conclusion (text "milestone-reached") (trace-id "meta-milestone-100"))))

(defrule meta-milestone-200
  (self-state (key "rule-count") (value ?v&:(>= ?v 200)))
  =>
  (assert (conclusion (text "milestone-reached") (trace-id "meta-milestone-200"))))

(defrule meta-knowledge-saturation
  (self-state (key "rule-count") (value ?v&:(>= ?v 200)))
  =>
  (assert (self-state (key "knowledge-saturation") (value "high"))))

(defrule meta-high-induction-conclusion
  (self-state (key "high-induction-rate") (value ?v))
  =>
  (assert (conclusion (text "high-induction-rate") (trace-id "meta-high-induction-conclusion"))))

(defrule meta-family-conclusion
  (self-state (key "family-member") (value ?p))
  =>
  (assert (conclusion (text "rule-family-known") (trace-id "meta-family-conclusion"))))

(defrule meta-conflict-conclusion
  (self-state (key "rule-conflict") (value ?x))
  =>
  (assert (conclusion (text "rule-conflict") (trace-id "meta-conflict-conclusion"))))

; ---------------- Expanded Self-referential rules (10) ----------------
(defrule self-gap-domain-awareness
  (self-state (key "knowledge-gap") (value ?domain))
  =>
  (assert (self-state (key "gap-domain") (value ?domain))))

(defrule self-session-summary-signal
  (conversation-topic (topic ?t1))
  (conversation-topic (topic ?t2))
  (conversation-topic (topic ?t3))
  =>
  (assert (conclusion (text "session-summary") (trace-id "self-session-summary-signal"))))

(defrule self-confidence-monitor-low
  (rule-health (rule-name ?r1) (confidence ?c1&:(< ?c1 0.5)))
  =>
  (assert (self-state (key "low-confidence-state") (value ?r1))))

(defrule self-improvement-tracking
  (self-state (key "accepted-ilp") (value ?n))
  =>
  (assert (self-state (key "self-growth") (value ?n))))

(defrule self-capability-boundary
  (intent (type "QUERY") (text ?t&:(or (neq (str-index "integral" (lowcase ?t)) FALSE) (neq (str-index "unsolved" (lowcase ?t)) FALSE))))
  (not (conclusion (text ?c) (trace-id ?id)))
  =>
  (assert (self-state (key "declare-incapable") (value ?t))))

(defrule self-introspective-query
  (intent (type "QUERY") (text ?t&:(neq (str-index "what do you know about" (lowcase ?t)) FALSE)))
  =>
  (assert (conclusion (text "introspective-response") (trace-id "self-introspective-query"))))

(defrule self-growth-conclusion
  (self-state (key "self-growth") (value ?v))
  =>
  (assert (conclusion (text "self-growth") (trace-id "self-growth-conclusion"))))

(defrule self-gap-conclusion
  (self-state (key "gap-domain") (value ?d))
  =>
  (assert (conclusion (text "gap-domain-known") (trace-id "self-gap-conclusion"))))

(defrule self-low-confidence-conclusion
  (self-state (key "low-confidence-state") (value ?r))
  =>
  (assert (conclusion (text "low-confidence-state") (trace-id "self-low-confidence-conclusion"))))

(defrule self-incapable-conclusion
  (self-state (key "declare-incapable") (value ?x))
  =>
  (assert (conclusion (text "declare-incapable") (trace-id "self-incapable-conclusion"))))

; ---------------- Domain-specific bootstrapping rules (40) ----------------
(defrule domain-science-element-property (relation (subject ?e) (predicate "is-a") (object "element")) => (assert (relation (subject ?e) (predicate "has-property") (object "physical-property") (confidence 0.72))))
(defrule domain-science-element-chemical (relation (subject ?e) (predicate "is-a") (object "element")) => (assert (relation (subject ?e) (predicate "has-property") (object "chemical-property") (confidence 0.72))))
(defrule domain-science-reaction-reactants (relation (subject ?r) (predicate "is-a") (object "reaction")) => (assert (relation (subject ?r) (predicate "requires") (object "reactants") (confidence 0.76))))
(defrule domain-science-hypothesis-evidence (relation (subject ?h) (predicate "is-a") (object "hypothesis")) => (assert (relation (subject ?h) (predicate "requires") (object "evidence") (confidence 0.8))))
(defrule domain-science-theory-hypotheses (relation (subject ?t) (predicate "is-a") (object "theory")) => (assert (relation (subject ?t) (predicate "requires") (object "confirmed-hypotheses") (confidence 0.78))))
(defrule domain-science-experiment-testing (relation (subject ?e) (predicate "is-a") (object "experiment")) => (assert (relation (subject ?e) (predicate "enables") (object "hypothesis-testing") (confidence 0.82))))

(defrule domain-geo-city-settlement (relation (subject ?c) (predicate "is-a") (object "city")) => (assert (relation (subject ?c) (predicate "is-a") (object "settlement") (confidence 0.9))))
(defrule domain-geo-country-contains-city (relation (subject ?country) (predicate "contains") (object ?city)) (relation (subject ?city) (predicate "is-a") (object "city")) => (assert (relation (subject ?country) (predicate "contains-city") (object ?city) (confidence 0.85))))
(defrule domain-geo-continent-contains-country (relation (subject ?cont) (predicate "contains") (object ?country)) (relation (subject ?country) (predicate "is-a") (object "country")) => (assert (relation (subject ?cont) (predicate "contains-country") (object ?country) (confidence 0.85))))
(defrule domain-geo-capital-of (relation (subject ?city) (predicate "capital-of") (object ?country)) => (assert (relation (subject ?country) (predicate "has-capital") (object ?city) (confidence 0.9))))
(defrule domain-geo-border-symmetric (relation (subject ?a) (predicate "border-with") (object ?b)) => (assert (relation (subject ?b) (predicate "border-with") (object ?a) (confidence 0.9))))

(defrule domain-bio-organism-cell (relation (subject ?o) (predicate "is-a") (object "organism")) => (assert (relation (subject ?o) (predicate "has-a") (object "cell") (confidence 0.88))))
(defrule domain-bio-cell-energy (relation (subject ?c) (predicate "is-a") (object "cell")) => (assert (relation (subject ?c) (predicate "requires") (object "energy") (confidence 0.86))))
(defrule domain-bio-species-organism (relation (subject ?s) (predicate "is-a") (object "species")) => (assert (relation (subject ?s) (predicate "is-a") (object "organism") (confidence 0.9))))
(defrule domain-bio-predator-prey (relation (subject ?p) (predicate "is-a") (object "predator")) => (assert (relation (subject ?p) (predicate "requires") (object "prey") (confidence 0.83))))
(defrule domain-bio-ecosystem-species (relation (subject ?e) (predicate "is-a") (object "ecosystem")) => (assert (relation (subject ?e) (predicate "contains") (object "species") (confidence 0.87))))
(defrule domain-bio-evolution-speciation (relation (subject ?e) (predicate "is-a") (object "evolution")) => (assert (relation (subject ?e) (predicate "causes") (object "speciation") (confidence 0.84))))

(defrule domain-math-proof-axioms (relation (subject ?p) (predicate "is-a") (object "proof")) => (assert (relation (subject ?p) (predicate "requires") (object "axioms") (confidence 0.88))))
(defrule domain-math-theorem-proof (relation (subject ?t) (predicate "is-a") (object "theorem")) => (assert (relation (subject ?t) (predicate "requires") (object "proof") (confidence 0.9))))
(defrule domain-math-lemma-theorem (relation (subject ?l) (predicate "is-a") (object "lemma")) => (assert (relation (subject ?l) (predicate "enables") (object "theorem") (confidence 0.84))))
(defrule domain-math-conjecture-lacks-proof (relation (subject ?c) (predicate "is-a") (object "conjecture")) => (assert (relation (subject ?c) (predicate "lacks") (object "proof") (confidence 0.9))))
(defrule domain-math-counterexample-prevents (relation (subject ?x) (predicate "is-a") (object "counterexample")) => (assert (relation (subject ?x) (predicate "prevents") (object "conjecture-acceptance") (confidence 0.85))))

(defrule domain-tech-software-hardware (relation (subject ?s) (predicate "is-a") (object "software")) => (assert (relation (subject ?s) (predicate "requires") (object "hardware") (confidence 0.9))))
(defrule domain-tech-api-integration (relation (subject ?a) (predicate "is-a") (object "api")) => (assert (relation (subject ?a) (predicate "enables") (object "integration") (confidence 0.88))))
(defrule domain-tech-framework-development (relation (subject ?f) (predicate "is-a") (object "framework")) => (assert (relation (subject ?f) (predicate "enables") (object "development") (confidence 0.86))))
(defrule domain-tech-bug-deployment (relation (subject ?b) (predicate "is-a") (object "bug")) => (assert (relation (subject ?b) (predicate "prevents") (object "deployment") (confidence 0.87))))
(defrule domain-tech-test-validation (relation (subject ?t) (predicate "is-a") (object "test")) => (assert (relation (subject ?t) (predicate "enables") (object "validation") (confidence 0.85))))
(defrule domain-tech-deployment-tests (relation (subject ?d) (predicate "is-a") (object "deployment")) => (assert (relation (subject ?d) (predicate "requires") (object "passing-tests") (confidence 0.89))))

(defrule domain-lang-word-definition (relation (subject ?w) (predicate "is-a") (object "word")) => (assert (relation (subject ?w) (predicate "has-a") (object "definition") (confidence 0.9))))
(defrule domain-lang-sentence-words (relation (subject ?s) (predicate "is-a") (object "sentence")) => (assert (relation (subject ?s) (predicate "contains") (object "words") (confidence 0.88))))
(defrule domain-lang-grammar-parsing (relation (subject ?g) (predicate "is-a") (object "grammar")) => (assert (relation (subject ?g) (predicate "enables") (object "parsing") (confidence 0.87))))
(defrule domain-lang-synonym-property (relation (subject ?s) (predicate "is-a") (object "synonym")) => (assert (relation (subject ?s) (predicate "has-property") (object "similar-meaning") (confidence 0.84))))
(defrule domain-lang-antonym-property (relation (subject ?a) (predicate "is-a") (object "antonym")) => (assert (relation (subject ?a) (predicate "has-property") (object "opposite-meaning") (confidence 0.84))))

(defrule domain-soc-institution-members (relation (subject ?i) (predicate "is-a") (object "institution")) => (assert (relation (subject ?i) (predicate "contains") (object "members") (confidence 0.86))))
(defrule domain-soc-law-enforcement (relation (subject ?l) (predicate "is-a") (object "law")) => (assert (relation (subject ?l) (predicate "enables") (object "enforcement") (confidence 0.89))))
(defrule domain-soc-rights-law (relation (subject ?r) (predicate "is-a") (object "rights")) => (assert (relation (subject ?r) (predicate "requires") (object "law") (confidence 0.83))))
(defrule domain-soc-economy-markets (relation (subject ?e) (predicate "is-a") (object "economy")) => (assert (relation (subject ?e) (predicate "contains") (object "markets") (confidence 0.85))))
(defrule domain-soc-market-buyers-sellers (relation (subject ?m) (predicate "is-a") (object "market")) => (assert (relation (subject ?m) (predicate "requires") (object "buyers-and-sellers") (confidence 0.88))))

(defrule domain-hist-event-subsequent (relation (subject ?e1) (predicate "before") (object ?e2)) => (assert (relation (subject ?e2) (predicate "after") (object ?e1) (confidence 0.89))))
(defrule domain-hist-cause-before-effect (relation (subject ?c) (predicate "causes") (object ?e)) => (assert (relation (subject ?c) (predicate "before") (object ?e) (confidence 0.91))))
(defrule domain-hist-era-events (relation (subject ?era) (predicate "contains") (object ?event)) => (assert (relation (subject ?event) (predicate "in-era") (object ?era) (confidence 0.86))))
(defrule domain-hist-revolution-change (relation (subject ?r) (predicate "is-a") (object "revolution")) => (assert (relation (subject ?r) (predicate "causes") (object "political-change") (confidence 0.85))))
(defrule domain-hist-war-conflict (relation (subject ?w) (predicate "is-a") (object "war")) => (assert (relation (subject ?w) (predicate "requires") (object "conflict") (confidence 0.88))))

; ---------------- Expanded verbalization templates (50+) ----------------
(deffacts expanded-templates
  (verbalization-template (pattern "capability-known") (template "I learned a capability relation from recent evidence."))
  (verbalization-template (pattern "kind-membership") (template "I recognized an entity membership relation."))
  (verbalization-template (pattern "causes-transitive-observed") (template "I observed a transitive causal chain."))
  (verbalization-template (pattern "related-observed") (template "I observed a relatedness pattern."))
  (verbalization-template (pattern "greeting-response") (template "Hello! I am ready to reason with you."))
  (verbalization-template (pattern "farewell-response") (template "Goodbye. I will keep monitoring knowledge updates."))
  (verbalization-template (pattern "topic-shift") (template "I detect that the topic changed."))
  (verbalization-template (pattern "new-entity") (template "A new entity was introduced into memory."))
  (verbalization-template (pattern "knowledge-gap") (template "I detected a knowledge gap for this query."))
  (verbalization-template (pattern "session-summary") (template "Session summary prepared from dominant topics."))
  (verbalization-template (pattern "high-induction-rate") (template "Induction activity is currently high."))
  (verbalization-template (pattern "milestone-reached") (template "Rulebase milestone reached."))
  (verbalization-template (pattern "source-conflict") (template "Sources disagree on this claim."))
  (verbalization-template (pattern "over-confirmation") (template "Potential confirmation bias detected."))
  (verbalization-template (pattern "root-cause-identified") (template "A root cause appears to be identified."))
  (verbalization-template (pattern "leaf-effect-identified") (template "A leaf effect appears in the causal graph."))
  (verbalization-template (pattern "group-precedes-target") (template "Multiple events precede the same target."))
  (verbalization-template (pattern "direct-sequence") (template "I inferred a direct temporal sequence."))
  (verbalization-template (pattern "sequence-known") (template "A temporal ordering has been recorded."))
  (verbalization-template (pattern "high-confidence-claim") (template "Several sources support this claim strongly."))
  (verbalization-template (pattern "belief-recorded") (template "A belief statement has been registered."))
  (verbalization-template (pattern "rule-family-known") (template "I detected a coherent family of rules."))
  (verbalization-template (pattern "rule-conflict") (template "I detected a conflict between inferred rules."))
  (verbalization-template (pattern "introspective-response") (template "I can summarize stored relations about requested entities."))
  (verbalization-template (pattern "self-growth") (template "My self-growth metric has been updated."))
  (verbalization-template (pattern "gap-domain-known") (template "I logged a domain-specific knowledge gap."))
  (verbalization-template (pattern "low-confidence-state") (template "Overall confidence appears low in parts of the rulebase."))
  (verbalization-template (pattern "declare-incapable") (template "This query is currently beyond my capability boundary."))
  (verbalization-template (pattern "instance-recognized") (template "I recognized an instance relation."))
  (verbalization-template (pattern "kind-chain") (template "I inferred a taxonomy chain through multiple kinds."))
  (verbalization-template (pattern "science-property") (template "Scientific property knowledge is available."))
  (verbalization-template (pattern "science-hypothesis") (template "Hypothesis and evidence requirements are known."))
  (verbalization-template (pattern "science-theory") (template "Theory formation constraints are loaded."))
  (verbalization-template (pattern "geo-settlement") (template "Geographical settlement relationships are loaded."))
  (verbalization-template (pattern "geo-capital") (template "Capital-city relations are available."))
  (verbalization-template (pattern "geo-border") (template "Border symmetry has been encoded."))
  (verbalization-template (pattern "bio-cell") (template "Biological cell dependencies are available."))
  (verbalization-template (pattern "bio-species") (template "Species and ecosystem relations are loaded."))
  (verbalization-template (pattern "bio-evolution") (template "Evolutionary causation patterns are available."))
  (verbalization-template (pattern "math-proof") (template "Proof and theorem dependencies are loaded."))
  (verbalization-template (pattern "math-conjecture") (template "Conjecture and counterexample rules are available."))
  (verbalization-template (pattern "tech-api") (template "Technology integration patterns are available."))
  (verbalization-template (pattern "tech-deployment") (template "Deployment dependencies are loaded."))
  (verbalization-template (pattern "lang-grammar") (template "Language parsing rules are loaded."))
  (verbalization-template (pattern "lang-semantics") (template "Lexical semantic patterns are available."))
  (verbalization-template (pattern "soc-law") (template "Societal law and rights relations are loaded."))
  (verbalization-template (pattern "soc-market") (template "Market structure constraints are known."))
  (verbalization-template (pattern "hist-era") (template "Historical era relations are available."))
  (verbalization-template (pattern "hist-revolution") (template "Historical revolution causation is loaded."))
  (verbalization-template (pattern "hist-war") (template "War and conflict dependency rules are known."))
  (verbalization-template (pattern "taxonomy-depth") (template "Taxonomy depth information is being tracked."))
  (verbalization-template (pattern "continuing-topic") (template "We are continuing the current topic."))
  (verbalization-template (pattern "repeated-query") (template "I detected a repeated query."))
  (verbalization-template (pattern "user-conflict") (template "I detected conflicting user assertions."))
  (verbalization-template (pattern "escalate-to-gap") (template "Repeated clarification requests escalated to a gap."))
  (verbalization-template (pattern "knowledge-saturation") (template "Knowledge saturation is high."))
  (verbalization-template (pattern "causal-support") (template "Supporting causal relations were observed."))
  (verbalization-template (pattern "timeline-grounded") (template "Timeline grounding against current time is available."))
  (verbalization-template (pattern "epistemic-closure") (template "Epistemic closure patterns are being tracked."))
  (verbalization-template (pattern "disambiguation-needed") (template "Entity disambiguation may be required.")))
