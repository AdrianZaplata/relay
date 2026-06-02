{{- define "relay.labels" -}}
app.kubernetes.io/part-of: relay
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{/* registry is optional: when empty (dev/kind, where images are loaded straight
     into the node's local store) render a bare "component:tag" instead of an
     invalid "/component:tag". Production sets image.registry and is unaffected. */}}
{{- define "relay.image" -}}
{{- if .Values.image.registry }}{{ .Values.image.registry }}/{{ end }}{{ .component }}:{{ .Values.image.tag }}
{{- end -}}

{{/* Shared RELAY_* env for the api and ingestor (same codebase, same config). */}}
{{- define "relay.backendEnv" -}}
- name: RELAY_DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ .Values.database.secretName }}
      key: {{ .Values.database.secretKey }}
- name: RELAY_KAFKA_BOOTSTRAP_SERVERS
  valueFrom:
    configMapKeyRef: { name: relay-config, key: kafka-bootstrap-servers }
- name: RELAY_TELEMETRY_TOPIC
  valueFrom:
    configMapKeyRef: { name: relay-config, key: telemetry-topic }
- name: RELAY_CONSUMER_GROUP
  valueFrom:
    configMapKeyRef: { name: relay-config, key: consumer-group }
- name: RELAY_LOG_LEVEL
  valueFrom:
    configMapKeyRef: { name: relay-config, key: log-level }
{{- end -}}
