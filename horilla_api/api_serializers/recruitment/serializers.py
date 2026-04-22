from django.contrib.auth.models import User
from django.db import IntegrityError
from rest_framework import serializers

from base.models import Company, Department, JobPosition
from employee.models import Employee
from recruitment.models import (
    Candidate,
    InterviewSchedule,
    Recruitment,
    RecruitmentSurvey,
    Skill,
    SkillZone,
    SkillZoneCandidate,
    Stage,
    SurveyTemplate,
)


class UserOrEmployeeRelatedField(serializers.PrimaryKeyRelatedField):
    default_error_messages = {
        "does_not_exist": 'Invalid pk "{pk_value}" - object does not exist.',
        "incorrect_type": "Incorrect type. Expected pk value, received {data_type}.",
    }

    def _ensure_employee_for_admin_user(self, user):
        if not (user.is_superuser or user.is_staff):
            self.fail("does_not_exist", pk_value=user.pk)
        employee, _created = Employee.objects.get_or_create(
            employee_user_id=user,
            defaults={
                "employee_first_name": user.first_name or user.username,
                "employee_last_name": user.last_name or "",
                "email": user.email or f"{user.username}-{user.id}@example.com",
                "phone": "0000000000",
                "role": "admin",
            },
        )
        updates = {}
        if not employee.email:
            updates["email"] = user.email or f"{user.username}-{user.id}@example.com"
        if not employee.phone:
            updates["phone"] = "0000000000"
        if (user.is_superuser or user.is_staff) and employee.role != "admin":
            updates["role"] = "admin"
        if updates:
            Employee.objects.filter(pk=employee.pk).update(**updates)
            for field, value in updates.items():
                setattr(employee, field, value)
        return employee

    def to_internal_value(self, data):
        if isinstance(data, dict):
            data = data.get("user_id") or data.get("employee_id") or data.get("id")
        if isinstance(data, str):
            data = data.strip()
        if isinstance(data, bool) or not isinstance(data, (str, int)):
            self.fail("incorrect_type", data_type=type(data).__name__)
        if isinstance(data, str):
            if not data.isdigit():
                self.fail("does_not_exist", pk_value=data)
            data = int(data)

        user = User.objects.filter(pk=data).first()
        if user:
            linked_employee = Employee.objects.filter(employee_user_id=user).first()
            if linked_employee:
                return linked_employee
            return self._ensure_employee_for_admin_user(user)

        employee = Employee.objects.filter(pk=data).first()
        if employee:
            return employee

        self.fail("does_not_exist", pk_value=data)


class RecruitmentPipelineSerializer(serializers.ModelSerializer):
    ALLOWED_COMPANIES = {"Ace Technologys", "Micronet Solutions"}
    DEFAULT_COMPANY_DETAILS = {
        "Ace Technologys": {
            "address": "Plot No 80, KT Nagar, Nagpur, Maharashtra 440013",
            "country": "India",
            "state": "Maharashtra",
            "city": "Nagpur",
            "zip": "440013",
        },
        "Micronet Solutions": {
            "address": "Plot No 80, KT Nagar, Nagpur, Maharashtra 440013",
            "country": "India",
            "state": "Nagpur",
            "city": "Maharashtra",
            "zip": "440013",
        },
    }

    job_position = serializers.JSONField(write_only=True)
    managers = serializers.ListField(
        child=serializers.JSONField(), write_only=True, allow_empty=False
    )
    company = serializers.JSONField(write_only=True)
    survey_templates = serializers.ListField(
        child=serializers.JSONField(), write_only=True, required=False, allow_empty=True
    )
    skills = serializers.ListField(
        child=serializers.JSONField(), write_only=True, required=False, allow_empty=True
    )

    job_position_data = serializers.SerializerMethodField(read_only=True)
    managers_data = serializers.SerializerMethodField(read_only=True)
    company_data = serializers.SerializerMethodField(read_only=True)
    survey_templates_data = serializers.SerializerMethodField(read_only=True)
    skills_data = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Recruitment
        fields = [
            "id",
            "title",
            "description",
            "job_position",
            "job_position_data",
            "managers",
            "managers_data",
            "start_date",
            "end_date",
            "vacancy",
            "company",
            "company_data",
            "survey_templates",
            "survey_templates_data",
            "skills",
            "skills_data",
        ]

    def _get_or_create_company(self, value):
        def validate_allowed(name):
            if name not in self.ALLOWED_COMPANIES:
                raise serializers.ValidationError(
                    {
                        "company": (
                            "Company must be either 'Ace Technologys' or "
                            "'Micronet Solutions'."
                        )
                    }
                )

        if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):
            company = Company.objects.filter(pk=int(value)).first()
            if company:
                validate_allowed(company.company)
                return company
            raise serializers.ValidationError(
                {"company": f'Invalid pk "{value}" - object does not exist.'}
            )

        if isinstance(value, str):
            company_name = value.strip()
            validate_allowed(company_name)
            company = Company.objects.filter(company__iexact=company_name).first()
            if company:
                return company
            return Company.objects.create(
                company=company_name,
                **self.DEFAULT_COMPANY_DETAILS[company_name],
            )

        if isinstance(value, dict):
            company_id = value.get("id")
            if company_id:
                company = Company.objects.filter(pk=company_id).first()
                if company:
                    validate_allowed(company.company)
                    return company
                raise serializers.ValidationError(
                    {"company": f'Invalid pk "{company_id}" - object does not exist.'}
                )

            required_fields = ["company", "address", "country", "state", "city", "zip"]
            missing = [field for field in required_fields if not value.get(field)]
            if missing:
                raise serializers.ValidationError(
                    {
                        "company": (
                            "To create a company, provide: company, address, country, "
                            "state, city, zip."
                        )
                    }
                )
            validate_allowed(value["company"])
            company, _ = Company.objects.get_or_create(
                company=value["company"],
                address=value["address"],
                defaults={
                    "country": value["country"],
                    "state": value["state"],
                    "city": value["city"],
                    "zip": value["zip"],
                },
            )
            return company

        raise serializers.ValidationError({"company": "Invalid company value."})

    def _get_default_department(self, company=None):
        department = Department.objects.filter(department__iexact="General").first()
        if not department:
            department = Department.objects.create(department="General")
        if company and not department.company_id.filter(pk=company.pk).exists():
            department.company_id.add(company)
        return department

    def _get_or_create_job_position(self, value, company=None):
        if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):
            job_position = JobPosition.objects.filter(pk=int(value)).first()
            if job_position:
                return job_position
            raise serializers.ValidationError(
                {"job_position": f'Invalid pk "{value}" - object does not exist.'}
            )

        if isinstance(value, str):
            job_position = JobPosition.objects.filter(
                job_position__iexact=value.strip()
            ).first()
            if job_position:
                if company and not job_position.company_id.filter(pk=company.pk).exists():
                    job_position.company_id.add(company)
                return job_position
            department = self._get_default_department(company=company)
            job_position = JobPosition.objects.create(
                job_position=value.strip(), department_id=department
            )
            if company:
                job_position.company_id.add(company)
            return job_position

        if isinstance(value, dict):
            job_position_id = value.get("id")
            if job_position_id:
                job_position = JobPosition.objects.filter(pk=job_position_id).first()
                if job_position:
                    return job_position
                raise serializers.ValidationError(
                    {
                        "job_position": (
                            f'Invalid pk "{job_position_id}" - object does not exist.'
                        )
                    }
                )

            title = value.get("job_position") or value.get("title") or value.get("name")
            if not title:
                raise serializers.ValidationError(
                    {"job_position": "Job position name is required."}
                )
            department_name = value.get("department") or "General"
            department = Department.objects.filter(
                department__iexact=department_name
            ).first()
            if not department:
                department = Department.objects.create(department=department_name)
            if company and not department.company_id.filter(pk=company.pk).exists():
                department.company_id.add(company)
            job_position, _ = JobPosition.objects.get_or_create(
                job_position=title,
                department_id=department,
            )
            if company and not job_position.company_id.filter(pk=company.pk).exists():
                job_position.company_id.add(company)
            return job_position

        raise serializers.ValidationError({"job_position": "Invalid job_position value."})

    def _resolve_manager(self, value):
        if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):
            value = int(value)
            employee = Employee.objects.filter(pk=value).first()
            if employee:
                return employee
            employee = Employee.objects.filter(employee_user_id__id=value).first()
            if employee:
                return employee
            raise serializers.ValidationError(
                {"managers": [f'Invalid pk "{value}" - object does not exist.']}
            )

        if isinstance(value, dict):
            candidate_keys = [value.get("id"), value.get("employee_id"), value.get("user_id")]
            for candidate in candidate_keys:
                if candidate:
                    return self._resolve_manager(candidate)
            email = value.get("email")
            if email:
                employee = Employee.objects.filter(email__iexact=email).first()
                if employee:
                    return employee

        raise serializers.ValidationError(
            {
                "managers": [
                    "Managers must contain employee ids, user ids, or objects with id/employee_id/user_id/email."
                ]
            }
        )

    def _get_or_create_survey_template(self, value, company=None):
        if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):
            template = SurveyTemplate.objects.filter(pk=int(value)).first()
            if template:
                return template
            raise serializers.ValidationError(
                {"survey_templates": [f'Invalid pk "{value}" - object does not exist.']}
            )

        if isinstance(value, str):
            template, _ = SurveyTemplate.objects.get_or_create(
                title=value.strip(),
                defaults={"company_id": company},
            )
            return template

        if isinstance(value, dict):
            template_id = value.get("id")
            if template_id:
                template = SurveyTemplate.objects.filter(pk=template_id).first()
                if template:
                    return template
                raise serializers.ValidationError(
                    {
                        "survey_templates": [
                            f'Invalid pk "{template_id}" - object does not exist.'
                        ]
                    }
                )
            title = value.get("title")
            if not title:
                raise serializers.ValidationError(
                    {"survey_templates": ["Survey template title is required."]}
                )
            template, _ = SurveyTemplate.objects.get_or_create(
                title=title.strip(),
                defaults={
                    "description": value.get("description"),
                    "company_id": company,
                },
            )
            return template

        raise serializers.ValidationError(
            {"survey_templates": ["Invalid survey template value."]}
        )

    def _get_or_create_skill(self, value):
        if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):
            skill = Skill.objects.filter(pk=int(value)).first()
            if skill:
                return skill
            raise serializers.ValidationError(
                {"skills": [f'Invalid pk "{value}" - object does not exist.']}
            )

        if isinstance(value, str):
            skill, _ = Skill.objects.get_or_create(title=value.strip())
            return skill

        if isinstance(value, dict):
            skill_id = value.get("id")
            if skill_id:
                skill = Skill.objects.filter(pk=skill_id).first()
                if skill:
                    return skill
                raise serializers.ValidationError(
                    {"skills": [f'Invalid pk "{skill_id}" - object does not exist.']}
                )
            title = value.get("title") or value.get("name")
            if not title:
                raise serializers.ValidationError(
                    {"skills": ["Skill title is required."]}
                )
            skill, _ = Skill.objects.get_or_create(title=title.strip())
            return skill

        raise serializers.ValidationError({"skills": ["Invalid skill value."]})

    def to_internal_value(self, data):
        internal = super().to_internal_value(data)

        company = self._get_or_create_company(internal["company"])
        job_position = self._get_or_create_job_position(internal["job_position"], company)
        managers = [self._resolve_manager(value) for value in internal["managers"]]
        survey_templates = [
            self._get_or_create_survey_template(value, company)
            for value in internal.get("survey_templates", [])
        ]
        skills = [self._get_or_create_skill(value) for value in internal.get("skills", [])]

        internal["company_id"] = company
        internal["job_position_id"] = job_position
        internal["recruitment_managers"] = managers
        internal["survey_templates"] = survey_templates
        internal["skills"] = skills

        internal.pop("company", None)
        internal.pop("job_position", None)
        internal.pop("managers", None)
        return internal

    def validate(self, attrs):
        attrs = super().validate(attrs)
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        vacancy = attrs.get("vacancy", getattr(self.instance, "vacancy", None))
        job_position = attrs.get(
            "job_position_id", getattr(self.instance, "job_position_id", None)
        )
        company = attrs.get("company_id", getattr(self.instance, "company_id", None))

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "End date cannot be less than start date."}
            )
        if vacancy is not None and vacancy <= 0:
            raise serializers.ValidationError(
                {"vacancy": "Vacancy must be greater than zero."}
            )
        if job_position and start_date:
            duplicate_qs = Recruitment.objects.filter(
                job_position_id=job_position,
                start_date=start_date,
            )
            if self.instance:
                duplicate_qs = duplicate_qs.exclude(pk=self.instance.pk)
            if duplicate_qs.exists():
                error = {
                    "job_position": (
                        "A recruitment already exists for this job position and start date."
                    ),
                    "start_date": (
                        "This start date is already used for the selected job position."
                    ),
                }
                if company:
                    error["company"] = (
                        "The selected company cannot reuse this job position and start date."
                    )
                raise serializers.ValidationError(error)
        return attrs

    def create(self, validated_data):
        managers = validated_data.pop("recruitment_managers", [])
        survey_templates = validated_data.pop("survey_templates", [])
        skills = validated_data.pop("skills", [])
        job_position = validated_data.get("job_position_id")

        try:
            recruitment = Recruitment.objects.create(
                **validated_data,
                is_event_based=False,
                closed=False,
                is_published=True,
            )
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "A recruitment with this job position and start date already exists."
                    ]
                }
            ) from exc
        recruitment.recruitment_managers.set(managers)
        recruitment.survey_templates.set(survey_templates)
        recruitment.skills.set(skills)
        if job_position:
            recruitment.open_positions.set([job_position])
        return recruitment

    def update(self, instance, validated_data):
        managers = validated_data.pop("recruitment_managers", None)
        survey_templates = validated_data.pop("survey_templates", None)
        skills = validated_data.pop("skills", None)
        job_position = validated_data.pop("job_position_id", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if job_position is not None:
            instance.job_position_id = job_position
        instance.save()

        if managers is not None:
            instance.recruitment_managers.set(managers)
        if survey_templates is not None:
            instance.survey_templates.set(survey_templates)
        if skills is not None:
            instance.skills.set(skills)
        if job_position is not None:
            instance.open_positions.set([job_position])

        return instance

    def get_job_position_data(self, obj):
        if not obj.job_position_id:
            return None
        return {
            "id": obj.job_position_id.id,
            "job_position": obj.job_position_id.job_position,
        }

    def get_managers_data(self, obj):
        return [
            {
                "id": employee.id,
                "name": employee.get_full_name(),
            }
            for employee in obj.recruitment_managers.all()
        ]

    def get_company_data(self, obj):
        if not obj.company_id:
            return None
        return {
            "id": obj.company_id.id,
            "company": obj.company_id.company,
        }

    def get_survey_templates_data(self, obj):
        return [
            {
                "id": template.id,
                "title": template.title,
            }
            for template in obj.survey_templates.all()
        ]

    def get_skills_data(self, obj):
        return [
            {
                "id": skill.id,
                "title": skill.title,
            }
            for skill in obj.skills.all()
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["job_position"] = data.pop("job_position_data")
        data["managers"] = data.pop("managers_data")
        data["company"] = data.pop("company_data")
        data["survey_templates"] = data.pop("survey_templates_data")
        data["skills"] = data.pop("skills_data")
        return data


class RecruitmentSurveyTemplateSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(
        source="company_id",
        queryset=Company.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    company_data = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SurveyTemplate
        fields = [
            "id",
            "title",
            "description",
            "company",
            "company_data",
        ]

    def _get_default_company(self):
        request = self.context.get("request")
        request_employee = getattr(getattr(request, "user", None), "employee_get", None)
        employee_company = (
            request_employee.get_company()
            if request_employee and hasattr(request_employee, "get_company")
            else None
        )
        return employee_company or Company.objects.filter(hq=True).first() or Company.objects.first()

    def to_internal_value(self, data):
        if hasattr(data, "copy"):
            mutable = data.copy()
        else:
            mutable = dict(data)

        company_value = mutable.get("company")
        if company_value not in (None, ""):
            try:
                company_pk = int(company_value)
            except (TypeError, ValueError):
                mutable.pop("company", None)
            else:
                if not Company.objects.filter(pk=company_pk).exists():
                    fallback_company = self._get_default_company()
                    if fallback_company:
                        mutable["company"] = str(fallback_company.pk)
                    else:
                        mutable.pop("company", None)

        return super().to_internal_value(mutable)

    def create(self, validated_data):
        if not validated_data.get("company_id"):
            fallback_company = self._get_default_company()
            if fallback_company:
                validated_data["company_id"] = fallback_company
        return super().create(validated_data)

    def get_company_data(self, obj):
        if not obj.company_id:
            return None
        return {"id": obj.company_id.id, "company": obj.company_id.company}

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["company"] = data.pop("company_data")
        return data


class RecruitmentSurveyQuestionSerializer(serializers.ModelSerializer):
    template = serializers.PrimaryKeyRelatedField(
        queryset=SurveyTemplate.objects.all(), write_only=True
    )
    recruitment = serializers.PrimaryKeyRelatedField(
        queryset=Recruitment.objects.all(), write_only=True
    )
    template_data = serializers.SerializerMethodField(read_only=True)
    recruitment_data = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = RecruitmentSurvey
        fields = [
            "id",
            "template",
            "template_data",
            "recruitment",
            "recruitment_data",
            "question",
            "sequence",
            "type",
        ]

    def validate_type(self, value):
        allowed = {choice[0] for choice in RecruitmentSurvey.question_types}
        if value not in allowed:
            raise serializers.ValidationError(
                f"Type must be one of: {', '.join(sorted(allowed))}."
            )
        return value

    def create(self, validated_data):
        template = validated_data.pop("template")
        recruitment = validated_data.pop("recruitment")
        instance = RecruitmentSurvey.objects.create(**validated_data)
        instance.template_id.set([template])
        instance.recruitment_ids.set([recruitment])
        if instance.job_position_ids.count() == 0 and recruitment.open_positions.exists():
            instance.job_position_ids.set(recruitment.open_positions.all())
        return instance

    def update(self, instance, validated_data):
        template = validated_data.pop("template", None)
        recruitment = validated_data.pop("recruitment", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if template is not None:
            instance.template_id.set([template])
        if recruitment is not None:
            instance.recruitment_ids.set([recruitment])
            instance.job_position_ids.set(recruitment.open_positions.all())
        return instance

    def get_template_data(self, obj):
        template = obj.template_id.first()
        if not template:
            return None
        return {"id": template.id, "title": template.title}

    def get_recruitment_data(self, obj):
        recruitment = obj.recruitment_ids.first()
        if not recruitment:
            return None
        return {"id": recruitment.id, "title": recruitment.title}

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["template"] = data.pop("template_data")
        data["recruitment"] = data.pop("recruitment_data")
        return data


class RecruitmentStageSerializer(serializers.ModelSerializer):
    recruitment = serializers.PrimaryKeyRelatedField(
        source="recruitment_id", queryset=Recruitment.objects.all(), write_only=True
    )
    stage_managers = UserOrEmployeeRelatedField(
        queryset=Employee.objects.all(), many=True, write_only=True
    )
    recruitment_data = serializers.SerializerMethodField(read_only=True)
    stage_managers_data = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Stage
        fields = [
            "id",
            "recruitment",
            "recruitment_data",
            "stage_managers",
            "stage_managers_data",
            "stage",
            "stage_type",
        ]
        validators = []

    def validate_stage_type(self, value):
        allowed = {choice[0] for choice in Stage.stage_types}
        if value not in allowed:
            raise serializers.ValidationError(
                "Stage Type must be one of: Initial, Applied, Test, Interview, Cancelled, Hired."
            )
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        recruitment = attrs.get("recruitment_id", getattr(self.instance, "recruitment_id", None))
        stage_name = attrs.get("stage", getattr(self.instance, "stage", None))
        if recruitment and stage_name:
            duplicate_qs = Stage.objects.filter(recruitment_id=recruitment, stage=stage_name)
            if self.instance:
                duplicate_qs = duplicate_qs.exclude(pk=self.instance.pk)
            if duplicate_qs.exists():
                raise serializers.ValidationError(
                    {"stage": "This stage already exists for the selected recruitment."}
                )
        return attrs

    def create(self, validated_data):
        stage_managers = validated_data.pop("stage_managers", [])
        instance = Stage.objects.create(**validated_data)
        instance.stage_managers.set(stage_managers)
        return instance

    def update(self, instance, validated_data):
        stage_managers = validated_data.pop("stage_managers", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if stage_managers is not None:
            instance.stage_managers.set(stage_managers)
        return instance

    def get_recruitment_data(self, obj):
        if not obj.recruitment_id:
            return None
        return {
            "id": obj.recruitment_id.id,
            "title": obj.recruitment_id.title,
        }

    def _get_stage_manager_employees(self, obj):
        stage_manager_ids = list(
            obj.stage_managers.through.objects.filter(stage_id=obj.id).values_list(
                "employee_id", flat=True
            )
        )
        stage_managers = [
            employee
            for employee_id, employee in Employee._base_manager.in_bulk(stage_manager_ids).items()
            if employee_id in stage_manager_ids
        ]
        if stage_managers:
            employee_map = {employee.id: employee for employee in stage_managers}
            return [
                employee_map[employee_id]
                for employee_id in stage_manager_ids
                if employee_id in employee_map
            ]
        if obj.recruitment_id:
            recruitment_manager_ids = list(
                obj.recruitment_id.recruitment_managers.through.objects.filter(
                    recruitment_id=obj.recruitment_id.id
                ).values_list("employee_id", flat=True)
            )
            recruitment_manager_map = Employee._base_manager.in_bulk(
                recruitment_manager_ids
            )
            return [
                recruitment_manager_map[employee_id]
                for employee_id in recruitment_manager_ids
                if employee_id in recruitment_manager_map
            ]
        return []

    def get_stage_managers_data(self, obj):
        return [
            {
                "id": employee.id,
                "name": employee.get_full_name(),
            }
            for employee in self._get_stage_manager_employees(obj)
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["recruitment"] = data.pop("recruitment_data")
        data["stage_managers"] = data.pop("stage_managers_data")
        return data


# class RecruitmentInterviewSerializer(serializers.ModelSerializer):
#     candidate = serializers.PrimaryKeyRelatedField(
#         source="candidate_id", queryset=Recruitment.objects.none(), write_only=True
#     )
#     interviewers = serializers.PrimaryKeyRelatedField(
#     source="employee_id",
#     queryset=Employee._base_manager.all(),   # ✅ here only
#     many=True,
#     write_only=True
# )
#     candidate_data = serializers.SerializerMethodField(read_only=True)
#     interviewers_data = serializers.SerializerMethodField(read_only=True)

#     class Meta:
#         model = InterviewSchedule
#         fields = [
#             "id",
#             "candidate",
#             "candidate_data",
#             "interviewers",
#             "interviewers_data",
#             "interview_date",
#             "interview_time",
#             "description",
#             "completed",
#         ]

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         from recruitment.models import Candidate

#         self.fields["candidate"].queryset = Candidate.objects.all()

#     # def create(self, validated_data):
#     #     interviewers = validated_data.pop("employee_id", [])
#     #     instance = InterviewSchedule.objects.create(**validated_data)
#     #     instance.employee_id.set(interviewers)
#     #     return instance

#     def create(self, validated_data):
#         interviewers = validated_data.pop("employee_id", [])
        
#         print("🔥 Interviewers received:", interviewers)   # 👈 DEBUG
        
#         instance = InterviewSchedule.objects.create(**validated_data)
#         instance.employee_id.set(interviewers)

#         print("🔥 Saved interviewers:", instance.employee_id.all())  # 👈 DEBUG

#         return instance

#     def update(self, instance, validated_data):
#         interviewers = validated_data.pop("employee_id", None)
#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         instance.save()
#         if interviewers is not None:
#             instance.employee_id.set(interviewers)
#         return instance

#     def get_candidate_data(self, obj):
#         candidate = obj.candidate_id
#         return {
#             "id": candidate.id,
#             "name": candidate.name,
#             "email": candidate.email,
#         }

#     def get_interviewers_data(self, obj):
#         return [
#             {"id": emp.id, "name": emp.get_full_name()}
#             for emp in obj.employee_id.all()
#         ]

  
#     def to_representation(self, instance):
#         data = super().to_representation(instance)
#         data["candidate"] = data.pop("candidate_data")
#         data["interviewers"] = data.pop("interviewers_data")
#         return data

class RecruitmentInterviewSerializer(serializers.ModelSerializer):
    candidate = serializers.PrimaryKeyRelatedField(
        source="candidate_id",
        queryset=Recruitment.objects.none(),
        write_only=True
    )

    interviewers = serializers.PrimaryKeyRelatedField(
        source="employee_id",
        queryset=Employee._base_manager.all(),
        many=True,
        write_only=True
    )

    candidate_data = serializers.SerializerMethodField(read_only=True)
    interviewers_data = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = InterviewSchedule
        fields = [
            "id",
            "candidate",
            "candidate_data",
            "interviewers",
            "interviewers_data",
            "interview_date",
            "interview_time",
            "description",
            "completed",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from recruitment.models import Candidate
        self.fields["candidate"].queryset = Candidate.objects.all()

    # ✅ FIX: Handle multiple input formats
    def to_internal_value(self, data):
        interviewers = data.get("interviewers")
        
        if interviewers:
            # If single value → convert to list
            if isinstance(interviewers, str) and "," not in interviewers:
                data["interviewers"] = [int(interviewers)]

            # If comma-separated string → convert to list
            elif isinstance(interviewers, str) and "," in interviewers:
                data["interviewers"] = [int(i.strip()) for i in interviewers.split(",")]

            # If tuple (form-data case)
            elif isinstance(interviewers, tuple):
                data["interviewers"] = list(interviewers)

        return super().to_internal_value(data)


    def create(self, validated_data):
        validated_data.pop("employee_id", None)  # ignore here
        return InterviewSchedule.objects.create(**validated_data)



    def update(self, instance, validated_data):
        interviewers = validated_data.pop("employee_id", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if interviewers is not None:
            instance.employee_id.clear()
            for emp in interviewers:
                instance.employee_id.add(emp)

        return instance

    def get_candidate_data(self, obj):
        candidate = obj.candidate_id
        return {
            "id": candidate.id,
            "name": candidate.name,
            "email": candidate.email,
        }

    def get_interviewers_data(self, obj):
        # Get all interviewers including inactive ones by using the through model
        through_objects = obj.employee_id.through.objects.filter(interviewschedule=obj)
        return [
            {"id": through.employee.id, "name": through.employee.get_full_name()}
            for through in through_objects
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["candidate"] = data.pop("candidate_data")
        data["interviewers"] = data.pop("interviewers_data")
        return data


        


class RecruitmentSkillZoneSerializer(serializers.ModelSerializer):
    skill_zone = serializers.CharField(source="title")
    company = serializers.PrimaryKeyRelatedField(
        source="company_id", queryset=Company.objects.all(), write_only=True
    )

    class Meta:
        model = SkillZone
        fields = [
            "id",
            "skill_zone",
            "description",
            "company",
        ]

    def to_representation(self, instance):
        return {
            "id": instance.id,
            "Skill Zone": instance.title,
            "Description": instance.description,
            "Company": getattr(instance.company_id, "company", None),
        }


class RecruitmentSkillZoneCandidateSerializer(serializers.ModelSerializer):
    skill_zone = serializers.PrimaryKeyRelatedField(
        source="skill_zone_id", queryset=SkillZone.objects.all()
    )
    candidate = serializers.PrimaryKeyRelatedField(
        source="candidate_id", queryset=Candidate.objects.all()
    )

    class Meta:
        model = SkillZoneCandidate
        fields = [
            "id",
            "skill_zone",
            "candidate",
            "reason",
            "added_on",
        ]
        read_only_fields = ["added_on"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        skill_zone = attrs.get(
            "skill_zone_id",
            getattr(self.instance, "skill_zone_id", None),
        )
        candidate = attrs.get(
            "candidate_id",
            getattr(self.instance, "candidate_id", None),
        )

        if skill_zone and candidate:
            queryset = SkillZoneCandidate.objects.filter(
                skill_zone_id=skill_zone,
                candidate_id=candidate,
            )
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    {
                        "candidate": "This candidate already exists in this skill zone."
                    }
                )
        return attrs

    def to_representation(self, instance):
        return {
            "id": instance.id,
            "skill_zone": {
                "id": getattr(instance.skill_zone_id, "id", None),
                "title": getattr(instance.skill_zone_id, "title", None),
            },
            "candidate": {
                "id": getattr(instance.candidate_id, "id", None),
                "name": getattr(instance.candidate_id, "name", None),
            },
            "reason": instance.reason,
            "added_on": instance.added_on,
        }
