"""Adjudicated decision catalog for the 42-query confirmation set.

Every candidate triple starts as NEGATIVE; only triples listed here are lifted.
  POS: (output, "table.column", evidence_type)   evidence_type in DATA/CONTROL/MIXED/INDIRECT
  UNK: (output, "table.column", note)            plausible causal path, no single-cell witness
                                                on this instance (type mismatch / empty literal
                                                filter / conjunctive predicates)

NEGATIVE reasons are attached automatically by tools/build_sheets.py.
"""

CATALOG = {
    # ---------------- case ----------------
    "synth-case-002": {
        "POS": [
            ("name", "singer.name", "DATA"),
            ("country", "singer.country", "DATA"),
            ("age", "singer.age", "DATA"),
            ("bucket", "singer.age", "CONTROL"),
        ],
        "UNK": [],
    },
    "synth-case-006": {
        "POS": [
            ("max(capacity)", "stadium.capacity", "DATA"),
            ("average", "stadium.average", "DATA"),
            ("average", "stadium.capacity", "INDIRECT"),
        ],
        "UNK": [],
    },
    "synth-case-008": {
        "POS": [
            ("name", "stadium.name", "DATA"),
            ("capacity", "stadium.capacity", "DATA"),
            ("name", "stadium.average", "CONTROL"),
            ("capacity", "stadium.average", "CONTROL"),
            ("bucket", "stadium.capacity", "CONTROL"),
        ],
        "UNK": [],
    },
    "synth-case-012": {
        "POS": [
            ("concert_name", "concert.concert_name", "DATA"),
            ("concert_name", "concert.concert_id", "MIXED"),
            ("theme", "concert.theme", "DATA"),
            ("theme", "concert.concert_id", "MIXED"),
            ("count(*)", "concert.concert_id", "CONTROL"),
            ("count(*)", "singer_in_concert.concert_id", "CONTROL"),
            ("concert_name", "singer_in_concert.concert_id", "CONTROL"),
            ("theme", "singer_in_concert.concert_id", "CONTROL"),
            ("bucket", "concert.concert_id", "INDIRECT"),
            ("bucket", "singer_in_concert.concert_id", "INDIRECT"),
        ],
        "UNK": [],
    },
    "synth-case-014": {
        "POS": [
            ("count(*)", "concert.stadium_id", "CONTROL"),
            ("bucket", "concert.stadium_id", "INDIRECT"),
        ],
        "UNK": [
            ("count(*)", "stadium.capacity", "标量子查询决定参与比较的 id；本实例两侧类型不一致（TEXT 对 REAL），单格扰动未观测到变化"),
            ("count(*)", "stadium.stadium_id", "同上：子查询返回的 id 只能通过类型强制影响比较"),
            ("bucket", "stadium.capacity", "同上，且 bucket 由 count 派生"),
            ("bucket", "stadium.stadium_id", "同上"),
        ],
    },
    "synth-case-016": {
        "POS": [("count(*)", "Pets.weight", "CONTROL")],
        "UNK": [],
    },
    # ---------------- cte ----------------
    "synth-cte-002": {
        "POS": [
            ("name", "singer.name", "DATA"),
            ("country", "singer.country", "DATA"),
            ("age", "singer.age", "DATA"),
        ],
        "UNK": [],
    },
    "synth-cte-006": {
        "POS": [
            ("song_name", "singer.song_name", "DATA"),
            ("song_release_year", "singer.song_release_year", "DATA"),
            ("song_name", "singer.age", "CONTROL"),
            ("song_release_year", "singer.age", "CONTROL"),
        ],
        "UNK": [],
    },
    "synth-cte-010": {
        "POS": [
            ("country", "singer.country", "MIXED"),
            ("count(*)", "singer.country", "CONTROL"),
        ],
        "UNK": [],
    },
    "synth-cte-012": {
        "POS": [
            ("song_name", "singer.song_name", "DATA"),
            ("song_name", "singer.age", "CONTROL"),
        ],
        "UNK": [],
    },
    "synth-cte-014": {
        "POS": [
            ("max(capacity)", "stadium.capacity", "DATA"),
            ("average", "stadium.average", "DATA"),
            ("average", "stadium.capacity", "INDIRECT"),
        ],
        "UNK": [],
    },
    # ---------------- aggregate ----------------
    "validation-00000": {"POS": [], "UNK": []},
    "validation-00004": {
        "POS": [
            ("avg(age)", "singer.country", "CONTROL"),
            ("min(age)", "singer.country", "CONTROL"),
            ("max(age)", "singer.country", "CONTROL"),
        ],
        "UNK": [
            ("avg(age)", "singer.age", "过滤 country='France' 在本实例上无匹配行，聚合恒为 NULL，单格改 age 不改变输出"),
            ("min(age)", "singer.age", "同上：聚合在空集上求值"),
            ("max(age)", "singer.age", "同上：聚合在空集上求值"),
        ],
    },
    "validation-00010": {
        "POS": [
            ("Country", "singer.country", "MIXED"),
            ("count(*)", "singer.country", "CONTROL"),
        ],
        "UNK": [],
    },
    "validation-00016": {
        "POS": [
            ("max(capacity)", "stadium.capacity", "DATA"),
            ("Average", "stadium.average", "DATA"),
            ("Average", "stadium.capacity", "INDIRECT"),
        ],
        "UNK": [],
    },
    "validation-00017": {
        "POS": [
            ("avg(capacity)", "stadium.capacity", "DATA"),
            ("max(capacity)", "stadium.capacity", "DATA"),
        ],
        "UNK": [],
    },
    "validation-00026": {"POS": [("Year", "concert.year", "MIXED")], "UNK": []},
    "validation-00043": {
        "POS": [("count(*)", "concert.stadium_id", "CONTROL")],
        "UNK": [
            ("count(*)", "stadium.capacity", "子查询按 capacity 选 id，但本实例 concert.stadium_id 为文本、stadium.stadium_id 为数值，单格扰动未观测到变化"),
            ("count(*)", "stadium.stadium_id", "同上：类型不一致导致比较失效"),
        ],
    },
    "validation-00049": {
        "POS": [
            ("max(weight)", "Pets.weight", "DATA"),
            ("max(weight)", "Pets.pettype", "CONTROL"),
            ("PetType", "Pets.pettype", "MIXED"),
        ],
        "UNK": [],
    },
    "validation-00053": {
        "POS": [],
        "UNK": [
            ("count(*)", "Student.sex", "WHERE sex='F' 与 pettype='dog' 为合取条件；实例上无行同时满足，单格扰动只能改一个条件"),
            ("count(*)", "Pets.pettype", "同上：另一个合取条件未满足"),
            ("count(*)", "Student.stuid", "连接键；合取过滤使结果恒为 0，单格改连接键不可观测"),
            ("count(*)", "Has_Pet.stuid", "同上"),
            ("count(*)", "Has_Pet.petid", "同上"),
            ("count(*)", "Pets.petid", "同上"),
        ],
    },
    "validation-00071": {
        "POS": [
            ("avg(pet_age)", "Pets.pet_age", "DATA"),
            ("max(pet_age)", "Pets.pet_age", "DATA"),
            ("avg(pet_age)", "Pets.pettype", "CONTROL"),
            ("max(pet_age)", "Pets.pettype", "CONTROL"),
            ("PetType", "Pets.pettype", "MIXED"),
        ],
        "UNK": [],
    },
    # ---------------- join ----------------
    "validation-00061": {
        "POS": [
            ("Major", "Student.major", "DATA"),
            ("Age", "Student.age", "DATA"),
            ("Major", "Pets.pettype", "CONTROL"),
            ("Age", "Pets.pettype", "CONTROL"),
        ],
        "UNK": [
            ("Major", "Student.stuid", "子查询因 pettype='cat' 无匹配而为空，连接键在单格扰动下不可观测"),
            ("Age", "Student.stuid", "同上"),
            ("Major", "Has_Pet.stuid", "同上"),
            ("Age", "Has_Pet.stuid", "同上"),
            ("Major", "Has_Pet.petid", "同上"),
            ("Age", "Has_Pet.petid", "同上"),
            ("Major", "Pets.petid", "同上"),
            ("Age", "Pets.petid", "同上"),
        ],
    },
    "validation-00063": {
        "POS": [
            ("StuID", "Student.stuid", "MIXED"),
            ("StuID", "Pets.pettype", "CONTROL"),
        ],
        "UNK": [
            ("StuID", "Has_Pet.stuid", "子查询因 cat 过滤为空，连接键不可观测"),
            ("StuID", "Has_Pet.petid", "同上"),
            ("StuID", "Pets.petid", "同上"),
        ],
    },
    "validation-00075": {
        "POS": [
            ("Fname", "Student.fname", "DATA"),
            ("Age", "Student.age", "DATA"),
            ("Fname", "Student.stuid", "CONTROL"),
            ("Age", "Student.stuid", "CONTROL"),
            ("Fname", "Has_Pet.stuid", "CONTROL"),
            ("Age", "Has_Pet.stuid", "CONTROL"),
        ],
        "UNK": [],
    },
    "validation-00095": {
        "POS": [
            ("Model", "car_names.model", "DATA"),
            ("Model", "car_names.makeid", "CONTROL"),
            ("Model", "cars_data.id", "CONTROL"),
            ("Model", "cars_data.horsepower", "CONTROL"),
        ],
        "UNK": [],
    },
    "validation-00133": {
        "POS": [
            ("Model", "car_names.model", "DATA"),
            ("Model", "car_names.makeid", "CONTROL"),
            ("Model", "cars_data.id", "CONTROL"),
            ("Model", "cars_data.mpg", "CONTROL"),
        ],
        "UNK": [],
    },
    "validation-00353": {
        "POS": [
            ("Template_Type_Description", "Ref_Template_Types.template_type_description", "DATA"),
            ("Template_Type_Description", "Ref_Template_Types.template_type_code", "CONTROL"),
            ("Template_Type_Description", "Templates.template_type_code", "CONTROL"),
            ("Template_Type_Description", "Templates.template_id", "CONTROL"),
            ("Template_Type_Description", "Documents.template_id", "CONTROL"),
        ],
        "UNK": [],
    },
    "validation-00399": {
        "POS": [
            ("Name", "teacher.name", "DATA"),
            ("Course", "course.course", "DATA"),
            ("Name", "course.course_id", "CONTROL"),
            ("Course", "course.course_id", "CONTROL"),
            ("Name", "course_arrange.course_id", "CONTROL"),
            ("Course", "course_arrange.course_id", "CONTROL"),
            ("Name", "course_arrange.teacher_id", "CONTROL"),
            ("Course", "course_arrange.teacher_id", "CONTROL"),
            ("Name", "teacher.teacher_id", "CONTROL"),
            ("Course", "teacher.teacher_id", "CONTROL"),
        ],
        "UNK": [],
    },
    "validation-00459": {
        "POS": [
            ("country_code", "players.country_code", "DATA"),
            ("first_name", "players.first_name", "DATA"),
            ("country_code", "players.player_id", "CONTROL"),
            ("first_name", "players.player_id", "CONTROL"),
            ("country_code", "rankings.player_id", "CONTROL"),
            ("first_name", "rankings.player_id", "CONTROL"),
            ("country_code", "rankings.tours", "CONTROL"),
            ("first_name", "rankings.tours", "CONTROL"),
        ],
        "UNK": [],
    },
    "validation-00505": {
        "POS": [
            ("name", "battle.name", "DATA"),
            ("result", "battle.result", "DATA"),
            ("bulgarian_commander", "battle.bulgarian_commander", "DATA"),
            ("name", "ship.location", "CONTROL"),
            ("result", "ship.location", "CONTROL"),
            ("bulgarian_commander", "ship.location", "CONTROL"),
        ],
        "UNK": [
            ("name", "battle.id", "连接键；实例上没有 ship.location='English Channel'，右表恒空，单格改 id 不可观测"),
            ("result", "battle.id", "同上"),
            ("bulgarian_commander", "battle.id", "同上"),
            ("name", "ship.lost_in_battle", "同上"),
            ("result", "ship.lost_in_battle", "同上"),
            ("bulgarian_commander", "ship.lost_in_battle", "同上"),
        ],
    },
    "validation-00545": {
        "POS": [
            ("course_name", "Courses.course_name", "DATA"),
            ("course_name", "Courses.course_id", "CONTROL"),
            ("course_name", "Student_Enrolment_Courses.course_id", "CONTROL"),
        ],
        "UNK": [],
    },
    "validation-00635": {
        "POS": [
            ("Country", "TV_Channel.country", "MIXED"),
            ("Country", "Cartoon.written_by", "CONTROL"),
        ],
        "UNK": [
            ("Country", "TV_Channel.id", "连接键；实例上 written_by='Todd Casey' 无匹配，右表恒空，单格改 id 不可观测"),
            ("Country", "Cartoon.channel", "同上"),
        ],
    },
    # ---------------- projection ----------------
    "validation-00002": {
        "POS": [
            ("Name", "singer.name", "DATA"),
            ("Country", "singer.country", "DATA"),
            ("Age", "singer.age", "DATA"),
        ],
        "UNK": [],
    },
    "validation-00006": {
        "POS": [
            ("Song_Name", "singer.song_name", "DATA"),
            ("Song_release_year", "singer.song_release_year", "DATA"),
            ("Song_Name", "singer.age", "CONTROL"),
            ("Song_release_year", "singer.age", "CONTROL"),
        ],
        "UNK": [],
    },
    "validation-00008": {
        "POS": [
            ("Country", "singer.country", "MIXED"),
            ("Country", "singer.age", "CONTROL"),
        ],
        "UNK": [],
    },
    "validation-00018": {
        "POS": [
            ("Name", "stadium.name", "DATA"),
            ("Capacity", "stadium.capacity", "DATA"),
            ("Name", "stadium.average", "CONTROL"),
            ("Capacity", "stadium.average", "CONTROL"),
        ],
        "UNK": [],
    },
    "validation-00028": {
        "POS": [
            ("Name", "stadium.name", "DATA"),
            ("Name", "stadium.stadium_id", "CONTROL"),
            ("Name", "concert.stadium_id", "CONTROL"),
        ],
        "UNK": [],
    },
    "validation-00067": {
        "POS": [
            ("PetType", "Pets.pettype", "DATA"),
            ("weight", "Pets.weight", "DATA"),
            ("PetType", "Pets.pet_age", "CONTROL"),
            ("weight", "Pets.pet_age", "CONTROL"),
        ],
        "UNK": [],
    },
    "validation-00155": {
        "POS": [
            ("Horsepower", "cars_data.horsepower", "DATA"),
            ("Horsepower", "cars_data.accelerate", "CONTROL"),
        ],
        "UNK": [],
    },
    "validation-00269": {
        "POS": [
            ("Manager_name", "shop.manager_name", "DATA"),
            ("District", "shop.district", "DATA"),
            ("Manager_name", "shop.number_products", "CONTROL"),
            ("District", "shop.number_products", "CONTROL"),
        ],
        "UNK": [],
    },
    "validation-00273": {
        "POS": [
            ("Name", "shop.name", "DATA"),
            ("Location", "shop.location", "DATA"),
            ("District", "shop.district", "DATA"),
        ],
        "UNK": [],
    },
    "validation-00281": {
        "POS": [
            ("Name", "employee.name", "DATA"),
            ("Name", "employee.employee_id", "CONTROL"),
            ("Name", "evaluation.employee_id", "CONTROL"),
        ],
        "UNK": [],
    },
}
