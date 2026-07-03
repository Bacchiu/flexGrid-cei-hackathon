{{/* Nome base del chart */}}
{{- define "eo.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Label comuni */}}
{{- define "eo.labels" -}}
app.kubernetes.io/name: {{ include "eo.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{/* FQDN del broker MQTT (raggiunto dall'edge nel namespace cloud) */}}
{{- define "eo.mqttHost" -}}
{{ .Values.mqtt.serviceName }}.{{ .Values.namespaces.cloud }}.svc.cluster.local
{{- end -}}
