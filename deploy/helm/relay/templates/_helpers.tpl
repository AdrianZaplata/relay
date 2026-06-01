{{- define "relay.labels" -}}
app.kubernetes.io/part-of: relay
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "relay.image" -}}
{{ .Values.image.registry }}/{{ .component }}:{{ .Values.image.tag }}
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
