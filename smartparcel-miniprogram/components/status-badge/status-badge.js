Component({ properties: { title: String, subtitle: String, status: String, item: Object }, methods: { tap() { this.triggerEvent('tap') } } })
